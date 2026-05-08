# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# pylint: disable=too-many-arguments
"""Host a LangGraph ``CompiledStateGraph`` as the Azure AI Invocations API.

Modeled after Microsoft Agent Framework's ``InvocationsHostServer``: pass a
graph, get a server.

Quick start::

    from azure.ai.agentserver.langgraph import InvocationsHostServer

    InvocationsHostServer(my_compiled_graph).run()
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Optional

from langchain_core.messages import AIMessageChunk
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from azure.ai.agentserver.invocations import InvocationAgentServerHost

from ._converters import (
    build_messages_input_from_text,
    extract_text,
    is_messages_state_schema,
    last_ai_message_text,
)

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)


class LangGraphInvocationsHostServer:
    """Host a LangGraph ``CompiledStateGraph`` as the Azure AI Invocations API.

    Body schema (mirrors Microsoft Agent Framework's
    ``InvocationsHostServer`` break-glass sample):

    .. code-block:: json

        { "message": "Hello!", "stream": false }

    Where:

    - ``message`` (required) — user message text.
    - ``stream`` (optional, default ``false``) — when ``true`` returns SSE
      with token deltas; when ``false`` returns a single JSON response.

    Multi-turn continuation uses the ``agent_session_id`` query param /
    ``x-agent-session-id`` header populated by
    :class:`InvocationAgentServerHost`.  The session id is forwarded to the
    graph as ``RunnableConfig.configurable.thread_id``, so any graph
    compiled with a checkpointer continues automatically.

    :param graph: The compiled LangGraph state graph to host.
    :type graph: CompiledStateGraph
    :keyword applicationinsights_connection_string: Forwarded to
        :class:`AgentServerHost`.
    :type applicationinsights_connection_string: str | None
    :keyword graceful_shutdown_timeout: Forwarded to
        :class:`AgentServerHost`.
    :type graceful_shutdown_timeout: int | None
    :raises ValueError: If the graph's state schema does not declare a
        ``messages`` field.  Override this class to host custom-state graphs.
    """

    def __init__(
        self,
        graph: "CompiledStateGraph",
        *,
        app: InvocationAgentServerHost | None = None,
        applicationinsights_connection_string: Optional[str] = None,
        graceful_shutdown_timeout: Optional[int] = None,
    ) -> None:
        self._validate_graph_schema(graph)
        self._graph = graph

        if app is not None:
            # Attach to an existing host (e.g. a multi-protocol mixin).
            # In this mode the host-level kwargs are ignored — the caller
            # is expected to have configured them on ``app`` itself.
            self._app = app
        else:
            host_kwargs: dict[str, Any] = {}
            if applicationinsights_connection_string is not None:
                host_kwargs["applicationinsights_connection_string"] = applicationinsights_connection_string
            if graceful_shutdown_timeout is not None:
                host_kwargs["graceful_shutdown_timeout"] = graceful_shutdown_timeout
            self._app = InvocationAgentServerHost(**host_kwargs)

        self._app.invoke_handler(self._handle_invoke)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def app(self) -> InvocationAgentServerHost:
        """The underlying :class:`InvocationAgentServerHost`."""
        return self._app

    @property
    def graph(self) -> "CompiledStateGraph":
        """The hosted compiled state graph."""
        return self._graph

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self, host: str = "0.0.0.0", port: Optional[int] = None) -> None:
        """Start the server synchronously.

        :param host: Network interface to bind. Defaults to ``"0.0.0.0"``.
        :type host: str
        :param port: Port to bind. Defaults to ``PORT`` env var or 8088.
        :type port: int | None
        """
        self._app.run(host=host, port=port)

    async def run_async(self, host: str = "0.0.0.0", port: Optional[int] = None) -> None:
        """Start the server asynchronously.

        :param host: Network interface to bind.
        :type host: str
        :param port: Port to bind.
        :type port: int | None
        """
        await self._app.run_async(host=host, port=port)

    # ------------------------------------------------------------------
    # Override hooks
    # ------------------------------------------------------------------

    async def parse_request(self, request: Request) -> tuple[str, bool]:
        """Parse the invocation request body.

        Default implementation reads ``{"message": str, "stream": bool}``.
        Override to support a different body schema.

        :param request: The Starlette request.
        :type request: Request
        :returns: ``(message, stream)`` tuple.
        :rtype: tuple[str, bool]
        :raises ValueError: If the body cannot be parsed or is missing the
            ``message`` field.
        """
        try:
            data = await request.json()
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")

        message = data.get("message")
        if not isinstance(message, str) or not message:
            raise ValueError("Request body must include a non-empty 'message' string.")

        stream = bool(data.get("stream", False))
        return message, stream

    def build_runnable_config(self, request: Request) -> dict[str, Any]:
        """Build a LangGraph ``RunnableConfig`` for the invocation.

        Sets ``configurable.thread_id`` from ``request.state.session_id`` so
        a graph compiled with a checkpointer naturally continues the right
        conversation across turns of the same session.

        :param request: The Starlette request.
        :type request: Request
        :returns: A ``RunnableConfig`` dict.
        :rtype: dict[str, Any]
        """
        session_id = getattr(request.state, "session_id", None)
        return {"configurable": {"thread_id": session_id or "default"}}

    def build_input(self, message: str) -> dict[str, Any]:
        """Build the LangGraph input from the parsed message.

        Default implementation produces ``{"messages": [HumanMessage(...)]}``.
        Override to support custom-state graphs.

        :param message: The user message text.
        :type message: str
        :returns: A LangGraph input value.
        :rtype: dict[str, Any]
        """
        return build_messages_input_from_text(message)

    # ------------------------------------------------------------------
    # Handler
    # ------------------------------------------------------------------

    async def _handle_invoke(self, request: Request) -> Response:
        try:
            message, stream = await self.parse_request(request)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

        graph_input = self.build_input(message)
        config = self.build_runnable_config(request)

        if stream:
            return StreamingResponse(
                self._stream_tokens(graph_input, config),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )

        try:
            state = await self._graph.ainvoke(graph_input, config=config)
        except Exception:  # pylint: disable=broad-except
            logger.exception("LangGraph invocation failed")
            return JSONResponse({"error": "Internal server error."}, status_code=500)

        text = last_ai_message_text(_messages_from_state(state))
        return JSONResponse({"response": text})

    async def _stream_tokens(
        self,
        graph_input: dict[str, Any],
        config: dict[str, Any],
    ) -> AsyncIterator[bytes]:
        try:
            async for chunk in self._graph.astream(graph_input, config=config, stream_mode="messages"):
                message_chunk = _extract_message_chunk(chunk)
                if message_chunk is None:
                    continue
                text = extract_text(message_chunk.content)
                if not text:
                    continue
                payload = json.dumps({"token": text}, ensure_ascii=False)
                yield f"data: {payload}\n\n".encode("utf-8")
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("LangGraph streaming invocation failed")
            payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
            yield f"event: error\ndata: {payload}\n\n".encode("utf-8")
            return

        yield b"event: done\ndata: {}\n\n"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_graph_schema(graph: "CompiledStateGraph") -> None:
        builder = getattr(graph, "builder", None)
        state_schema = getattr(builder, "state_schema", None) if builder is not None else None
        if state_schema is None:
            return
        if is_messages_state_schema(state_schema):
            return
        raise ValueError(
            "InvocationsHostServer's default request converter only supports "
            "graphs whose state schema declares a 'messages' field. Subclass "
            "InvocationsHostServer and override `build_input` (and optionally "
            "`parse_request`) to host custom-state graphs."
        )


def _messages_from_state(state: Any) -> list[Any]:
    if isinstance(state, dict):
        return list(state.get("messages") or [])
    return list(getattr(state, "messages", None) or [])


def _extract_message_chunk(chunk: Any) -> AIMessageChunk | None:
    if isinstance(chunk, AIMessageChunk):
        return chunk
    if isinstance(chunk, tuple) and chunk:
        candidate = chunk[0]
        if isinstance(candidate, AIMessageChunk):
            return candidate
    return None
