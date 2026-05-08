# Azure AI Agent Server — LangGraph adapter

A thin hosting adapter that exposes a [LangGraph](https://github.com/langchain-ai/langgraph) `CompiledStateGraph` as the Azure AI **Responses API** or **Invocations API** on top of the [`azure-ai-agentserver-*`](https://pypi.org/search/?q=azure-ai-agentserver) packages.

## Install

```bash
pip install azure-ai-agentserver-langgraph
```

## Quick start — Responses API

```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI

from azure.ai.agentserver.langgraph import ResponsesHostServer

graph = create_react_agent(AzureChatOpenAI(model="gpt-4o"), tools=[])

if __name__ == "__main__":
    ResponsesHostServer(graph).run()
```

```bash
curl -N -X POST http://localhost:8088/responses \
  -H 'Content-Type: application/json' \
  -d '{"input": "Hello!", "stream": true}'
```

Routes:

| Method | Path |
|--------|------|
| POST   | `/responses` |
| GET    | `/responses/{response_id}` |
| DELETE | `/responses/{response_id}` |
| POST   | `/responses/{response_id}/cancel` |
| GET    | `/responses/{response_id}/input_items` |
| GET    | `/healthy` |

## Quick start — Invocations API

```python
from azure.ai.agentserver.langgraph import InvocationsHostServer

InvocationsHostServer(graph).run()
```

```bash
# First turn
curl -i -X POST http://localhost:8088/invocations \
  -H 'Content-Type: application/json' \
  -d '{"message": "Hello!"}'

# Subsequent turn — pass the x-agent-session-id from the previous response
curl -X POST 'http://localhost:8088/invocations?agent_session_id=<id>' \
  -H 'Content-Type: application/json' \
  -d '{"message": "And again?"}'
```

Body schema: `{"message": str, "stream": bool = false}`. Streaming returns SSE token deltas.

Routes:

| Method | Path |
|--------|------|
| POST   | `/invocations` |
| GET    | `/invocations/{invocation_id}` |
| POST   | `/invocations/{invocation_id}/cancel` |
| GET    | `/invocations/docs/openapi.json` |
| GET    | `/healthy` |

## Conversation continuity

- **Responses API:** `previous_response_id` and `conversation` work via the configured `ResponseProviderProtocol` (in-memory by default; `FoundryStorageProvider` when running on Foundry).
- **Invocations API:** the resolved `agent_session_id` is forwarded to LangGraph as `RunnableConfig.configurable.thread_id`. Compile your graph with a checkpointer (`MemorySaver`, Redis, etc.) and turns of the same session continue automatically.

## Customising

Both `ResponsesHostServer` and `InvocationsHostServer` are normal classes —
subclass and override the `build_input` / `parse_request` / `handle_create`
hooks to support custom-state graphs or alternate request shapes. For full
control (custom routes, multi-protocol composition, custom request parsing)
drop down to the underlying packages directly:

```python
from azure.ai.agentserver.responses import ResponsesAgentServerHost

class MyHost(ResponsesAgentServerHost):
    pass

app = MyHost()

@app.response_handler
async def handler(request, context, cancellation_signal):
    ...

app.run()
```

## Default-converter constraints

The default converters require a graph whose state schema declares a
`messages` field (i.e. `MessagesState`-compatible). Constructing
`ResponsesHostServer` or `InvocationsHostServer` with a graph that does not
satisfy this constraint raises `ValueError`. To host such graphs, subclass
and override the input converter, or use the underlying packages directly.

## Feature parity vs. `1.0.0b17`

This package is a clean rewrite on top of the new
`azure-ai-agentserver-{core,responses,invocations}` stack. Some features
from the legacy `1.0.0b17` build are intentionally postponed. Use this
table to check whether your scenario is covered today.

| Capability | b17 | This package | Notes |
|---|:---:|:---:|---|
| **Hosting** |  |  |  |
| Host a `CompiledStateGraph` over OpenAI Responses API | ✅ | ✅ | Now via `ResponsesHostServer`, plus an Invocations host b17 didn't have. |
| Streaming SSE response lifecycle (per-token text deltas) | ✅ | ✅ | |
| Non-streaming response | ✅ | ✅ | |
| Multi-turn via `previous_response_id` / `conversation` | ✅ | ✅ | Provider-driven via `ResponseContext.get_history()`. |
| Multi-turn via `agent_session_id` (Invocations) | ❌ (no API) | ✅ | New protocol surface. |
| Mid-stream cancellation | ✅ | ✅ | Via the responses host's `cancellation_signal`. |
| Graceful shutdown | ✅ | ✅ | Inherited from `AgentServerHost`. |
| **Tool calls** |  |  |  |
| Tool call & tool result output items in non-streaming | ✅ | ✅ | `function_call` + `function_call_output` items, correlated by `call_id`. |
| Tool call & tool result output items in streaming | ✅ | ✅ | Via `stream_mode=["updates","messages"]`. |
| Per-token streaming of tool **arguments** | ✅ | ❌ | Currently emitted as a single delta, not partial fragments. |
| **Foundry tools** |  |  |  |
| `FoundryToolLike` / `ResolvedFoundryTool` | ✅ | ❌ | Postponed. |
| `use_foundry_tools()` | ✅ | ❌ | Postponed. |
| `FoundryToolLateBindingChatModel` | ✅ | ❌ | Postponed. |
| `FoundryToolBindingMiddleware` | ✅ | ❌ | Postponed. |
| `FoundryToolCallWrapper` / `FoundryToolNodeWrappers` | ✅ | ❌ | Postponed. |
| `OAuthConsentRequiredError` → `requires_action` SSE | ✅ | ❌ | Postponed. |
| **Foundry checkpointing** |  |  |  |
| `FoundryCheckpointSaver` (durable graph state on Foundry) | ✅ | ❌ | Postponed. Users get `MemorySaver` plus any LangGraph-supported checkpointer. |
| `FoundryCheckpointClient` integration | ✅ | ❌ | Postponed. Blocked on the new `-core` exposing the client. |
| **Human-in-the-Loop** |  |  |  |
| `interrupt()` + `Command(resume=...)` round-trip | ✅ | ❌ | Postponed. b17's `HumanInTheLoop*Helper` modules not ported. |
| Interrupt rendered as a structured response item | ✅ | ❌ | Pairs with `requires_action` event encoding. |
| **Conversation history fallback** |  |  |  |
| Auto-fetch from `AsyncOpenAI.conversations.items.list(...)` when no checkpoint | ✅ | ❌ (by design) | New design is provider-only — plug a `ResponseProviderProtocol` (e.g. `FoundryStorageProvider`) into `ResponsesHostServer(..., store=...)`. |
| Filter incomplete tool-call sequences | ✅ | ❌ | Same — provider-only. |
| **Tracing** |  |  |  |
| Azure Monitor / OTel via env vars | ✅ | ✅ | Inherited from `AgentServerHost`. |
| `LANGSMITH_OTEL_*` env wiring | ✅ | ❌ | Postponed. |
| `AzureAIOpenTelemetryTracer` callback registration | ✅ | ❌ | Postponed. |
| `service.namespace = "azure.ai.agentserver.langgraph"` span attribute | ✅ | ❌ | Trivial follow-up. |
| **Public API ergonomics** |  |  |  |
| `from_langgraph(graph)` one-liner | ✅ | ❌ | Replaced by `ResponsesHostServer(graph)` / `InvocationsHostServer(graph)`. |
| `LanggraphRunContext` exposed via `RunnableConfig` | ✅ | ❌ | New SDK has no equivalent context type. |
| Pluggable converter | ✅ (ABC) | partial | Override hooks (`build_input`, `build_runnable_config`, `handle_create`, `parse_request`) instead of an ABC. |
| **Workflows** |  |  |  |
| Custom multi-node `StateGraph` (non-`MessagesState`) | requires user converter | requires subclass | Both gate on `is_messages_state_schema()`; non-`MessagesState` graphs need user code. |
| `interrupt()` + `Command` in workflows | ✅ | ❌ | See HITL row. |

**Bottom line — what works today.** LangGraph agents (ReAct or
custom `MessagesState` graphs) where tools live in user code, multi-turn
via the standard mechanisms, and both Responses + Invocations APIs.

**Not yet covered.** Foundry-managed tools (the entire b17 `tools/`
module), `FoundryCheckpointSaver`, HITL `interrupt()` round-trips,
LangSmith / Azure-AI tracing callback wiring, and per-token streaming of
tool arguments. Open an issue if any of these block your migration.

## Contributing

This project welcomes contributions and suggestions. Most contributions
require you to agree to a Contributor License Agreement (CLA) declaring
that you have the right to, and actually do, grant us the rights to use
your contribution. For details, visit https://cla.microsoft.com.
