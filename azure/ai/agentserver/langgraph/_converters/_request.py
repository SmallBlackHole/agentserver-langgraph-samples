# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
"""Convert Responses API requests into LangGraph ``MessagesState`` input."""
from __future__ import annotations

import json
from typing import Any, Sequence

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.tool import ToolCall

from azure.ai.agentserver.responses.models import (
    FunctionCallOutputItemParam,
    ItemFunctionToolCall,
    ItemMessage,
    MessageContentInputTextContent,
    MessageContentOutputTextContent,
)


_ROLE_TO_MESSAGE_CLS: dict[str, type[AnyMessage]] = {
    "user": HumanMessage,
    "system": SystemMessage,
    "developer": SystemMessage,
    "assistant": AIMessage,
}


def items_to_messages(items: Sequence[Any]) -> list[AnyMessage]:
    """Translate resolved Responses API items into LangChain messages.

    Accepts the typed ``Item`` subtypes returned by
    :meth:`ResponseContext.get_input_items`.  Items that do not map cleanly
    to a LangChain message type are skipped.

    :param items: Resolved input items from the request.
    :type items: Sequence[Any]
    :return: A list of LangChain messages suitable for a ``MessagesState`` graph.
    :rtype: list[AnyMessage]
    """
    messages: list[AnyMessage] = []
    for item in items:
        message = _item_to_message(item)
        if message is not None:
            messages.append(message)
    return messages


def _item_to_message(item: Any) -> AnyMessage | None:
    if isinstance(item, ItemMessage):
        text = _content_to_text(item.content)
        role_value = getattr(item.role, "value", item.role)
        cls = _ROLE_TO_MESSAGE_CLS.get(str(role_value))
        if cls is None:
            return None
        return cls(content=text)

    if isinstance(item, ItemFunctionToolCall):
        try:
            args = json.loads(item.arguments) if item.arguments else {}
        except json.JSONDecodeError:
            args = {}
        return AIMessage(
            content="",
            tool_calls=[ToolCall(id=item.call_id, name=item.name, args=args)],
        )

    if isinstance(item, FunctionCallOutputItemParam):
        output = item.output
        if isinstance(output, list):
            output = _content_to_text(output)
        return ToolMessage(content=output or "", tool_call_id=item.call_id)

    return None


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, (MessageContentInputTextContent, MessageContentOutputTextContent)):
                if part.text:
                    parts.append(part.text)
            elif isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts)
    return str(content) if content is not None else ""


def build_messages_input(
    items: Sequence[Any],
    *,
    instructions: str | None = None,
) -> dict[str, list[AnyMessage]]:
    """Build a ``{"messages": [...]}`` LangGraph input from resolved items.

    Prepends a ``SystemMessage`` when *instructions* is non-empty.  Empty
    item lists yield an empty messages list — callers should typically have
    at least one user message before invoking the graph.

    :param items: Resolved input items from the request.
    :type items: Sequence[Any]
    :param instructions: Optional system instructions from the request.
    :type instructions: str | None
    :return: The ``{"messages": [...]}`` payload accepted by ``MessagesState`` graphs.
    :rtype: dict[str, list[AnyMessage]]
    """
    messages: list[AnyMessage] = []
    if instructions:
        messages.append(SystemMessage(content=instructions))
    messages.extend(items_to_messages(items))
    return {"messages": messages}


def build_messages_input_from_text(
    text: str,
    *,
    instructions: str | None = None,
) -> dict[str, list[AnyMessage]]:
    """Build a ``{"messages": [...]}`` payload from a single user text string.

    Convenience wrapper used by the Invocations converter when the body is
    already a plain string.

    :param text: The user's message text.
    :type text: str
    :param instructions: Optional system instructions.
    :type instructions: str | None
    :return: The ``{"messages": [...]}`` payload.
    :rtype: dict[str, list[AnyMessage]]
    """
    messages: list[AnyMessage] = []
    if instructions:
        messages.append(SystemMessage(content=instructions))
    if text:
        messages.append(HumanMessage(content=text))
    return {"messages": messages}
