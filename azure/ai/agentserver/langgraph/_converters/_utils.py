# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
"""Internal helpers: state-schema validation and message text extraction."""
from __future__ import annotations

from typing import Any, Iterable
from typing import get_type_hints

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage


def is_messages_state_schema(state_schema: Any) -> bool:
    """Return ``True`` when *state_schema* exposes a ``messages`` field.

    LangGraph compiles graphs against a TypedDict (or dataclass-like) state
    schema.  The default request/response converters only know how to build
    ``{"messages": [...]}`` payloads, so we fast-fail when the schema does
    not expose that key.

    :param state_schema: The state schema class associated with a compiled graph.
    :type state_schema: Any
    :return: ``True`` when the schema declares a ``messages`` field.
    :rtype: bool
    """
    fields = _get_typeddict_fields(state_schema)
    return "messages" in fields


def _get_typeddict_fields(schema_class: Any) -> dict[str, Any]:
    try:
        return get_type_hints(schema_class)
    except (TypeError, AttributeError):
        if hasattr(schema_class, "__annotations__"):
            return dict(schema_class.__annotations__)
    return {}


def extract_text(content: Any) -> str:
    """Return the plain-text representation of a LangChain message ``content``.

    LangChain message ``content`` is either a string or a list of content
    parts.  String parts are concatenated; non-string parts (images, files,
    tool-use blocks, etc.) are ignored for text extraction.

    :param content: The raw ``content`` field of a LangChain message.
    :type content: Any
    :return: The flattened text content.
    :rtype: str
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content)


def last_ai_message_text(messages: Iterable[Any]) -> str:
    """Return the text content of the last ``AIMessage`` in *messages*.

    Used by the default Invocations and non-streaming Responses converters to
    surface the assistant's final answer after a graph run.  When no
    ``AIMessage`` is present the function returns an empty string.

    :param messages: An iterable of LangChain messages, typically the
        ``messages`` channel from a graph result.
    :type messages: Iterable[Any]
    :return: The text content of the last ``AIMessage`` or ``""``.
    :rtype: str
    """
    last: BaseMessage | None = None
    for message in messages:
        if isinstance(message, AIMessage):
            last = message
    if last is None:
        return ""
    return extract_text(last.content)
