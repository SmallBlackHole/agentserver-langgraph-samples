# LangGraph hosting on `azure-ai-agentserver-{core,responses,invocations}`

> Status: **Draft**
> Date: 2026-05-07
> Owners: agentserver team
> Audience: contributors building the rewritten `azure-ai-agentserver-langgraph` package

---

## 1. Goal

Re-introduce `azure-ai-agentserver-langgraph` as a **thin hosting adapter** that lets a user expose an existing LangGraph `CompiledStateGraph` as either:

- the **Responses API** (`POST /responses`, SSE streaming, lifecycle, etc.) — backed by `azure-ai-agentserver-responses`, or
- the **Invocations API** (`POST /invocations`) — backed by `azure-ai-agentserver-invocations`,

…on top of the shared `AgentHost` from `azure-ai-agentserver-core`.

This is a **clean rewrite**. The legacy `1.0.0b17` source on the `azure-ai-agentserver-langgraph_1.0.0b17` tag is consulted as a behavioral reference only; nothing about its public API, module layout, or class names is contractually carried forward.

The user-facing contract is modeled after the equivalent adapter package for Microsoft Agent Framework:
[`agent_framework_foundry_hosting`](https://github.com/microsoft/agent-framework/tree/main/python/samples/04-hosting/foundry-hosted-agents).
That package exposes the agent through two top-level classes — `ResponsesHostServer(agent)` and `InvocationsHostServer(agent)` — each with a `.run()` method. We mirror that shape for LangGraph graphs.

---

## 2. Scope

### In scope

- Take a `CompiledStateGraph` (or anything LangGraph treats as one, including a `WorkflowBuilder(...).build().as_graph()` analogue) and serve it as a Responses API endpoint or Invocations API endpoint.
- Convert request payloads (`CreateResponse` / invocation JSON) into LangGraph input.
- Convert LangGraph output (final result and streaming updates) into Responses API event streams or Invocations JSON.
- Multi-turn continuation through the standard mechanisms already provided by the underlying packages:
  - For `/responses`: `previous_response_id`, `conversation` field, and the `ResponseProviderProtocol` plugged into `ResponseHandler`.
  - For `/invocations`: `agent_session_id` query/header propagation provided by `InvocationHandler` (state-management is the user's responsibility, mirroring the agent-framework break-glass sample).
- Sample apps and end-to-end tests.

### Explicitly out of scope (postponed)

These were part of `1.0.0b17` but are **not** included in this design and will be tackled in follow-up work:

- Foundry-hosted tools (`FoundryToolLike`, `OAuthConsentRequiredError`, `FoundryToolBindingMiddleware`, `FoundryToolLateBindingChatModel`, `FoundryToolNodeWrappers`, `use_foundry_tools`).
- Foundry checkpointing (`FoundryCheckpointSaver`, `FoundryCheckpointClient`).
- Human-in-the-loop interrupts / `Command` resumption helpers.
- Conversation-history fallback via `AsyncOpenAI`.
- LangSmith / Azure-AI tracing callback wiring beyond what `AgentHost` already does via `APPLICATIONINSIGHTS_CONNECTION_STRING` / `OTEL_EXPORTER_OTLP_ENDPOINT`.
- Anything related to publishing, versioning, or PyPI rollout.

If the user already has, e.g., a checkpointer compiled into their graph, it will just work — we simply do not provide one in this package.

---

## 3. User-facing API

### 3.1 Hosting a graph as the Responses API

```python
from langgraph.graph import StateGraph
from azure.ai.agentserver.langgraph import ResponsesHostServer

graph = build_my_graph()  # returns CompiledStateGraph

if __name__ == "__main__":
    ResponsesHostServer(graph).run()
```

`.run()` listens on `0.0.0.0:8088` (overridable) and serves:

| Method | Route                                       |
| ------ | ------------------------------------------- |
| POST   | `/responses`                                |
| GET    | `/responses/{response_id}`                  |
| DELETE | `/responses/{response_id}`                  |
| POST   | `/responses/{response_id}/cancel`           |
| GET    | `/responses/{response_id}/input_items`      |
| GET    | `/healthy`                                  |

### 3.2 Hosting a graph as the Invocations API

```python
from azure.ai.agentserver.langgraph import InvocationsHostServer

InvocationsHostServer(graph).run()
```

Serves `/invocations`, `/invocations/{id}`, `/invocations/{id}/cancel`, `/invocations/docs/openapi.json`, `/healthy`.

### 3.3 Class signatures

```python
class ResponsesHostServer:
    def __init__(
        self,
        graph: "CompiledStateGraph",
        *,
        # Pass-through to azure-ai-agentserver-responses.ResponseHandler:
        options: ResponsesServerOptions | None = None,
        provider: ResponseProviderProtocol | None = None,
        prefix: str = "",
        # Pass-through to azure-ai-agentserver-core.AgentHost:
        application_insights_connection_string: str | None = None,
        graceful_shutdown_timeout: int | None = None,
        log_level: str | None = None,
        # Optional override for advanced users:
        converter: "GraphResponsesConverter | None" = None,
    ) -> None: ...

    @property
    def server(self) -> AgentHost: ...
    @property
    def handler(self) -> ResponseHandler: ...

    def run(self, host: str = "0.0.0.0", port: int | None = None) -> None: ...
    async def run_async(self, host: str = "0.0.0.0", port: int | None = None) -> None: ...


class InvocationsHostServer:
    def __init__(
        self,
        graph: "CompiledStateGraph",
        *,
        # Pass-through to azure-ai-agentserver-core.AgentHost:
        application_insights_connection_string: str | None = None,
        graceful_shutdown_timeout: int | None = None,
        log_level: str | None = None,
        # Optional override for advanced users:
        converter: "GraphInvocationsConverter | None" = None,
    ) -> None: ...

    @property
    def server(self) -> AgentHost: ...
    @property
    def handler(self) -> InvocationHandler: ...

    def run(self, host: str = "0.0.0.0", port: int | None = None) -> None: ...
    async def run_async(self, host: str = "0.0.0.0", port: int | None = None) -> None: ...
```

Notes:

- Each class **owns its own `AgentHost`**. The common case is one host = one protocol. Users who genuinely need both protocols on the same host can fall back to the "break glass" path in §3.4 (which is just direct usage of the underlying packages — no extra surface area in this package).
- Exposing `.server` and `.handler` is the integration seam: anything not surfaced as a constructor kwarg is reachable through these (e.g. `host_server.handler.create_handler(...)` to override the handler post-hoc, or `host_server.server.shutdown_handler(...)` for custom shutdown logic).

### 3.4 "Break glass" — drop down to the underlying packages

For full control (custom routes, multiple protocols on one host, custom request parsing) the user **does not call into this package at all**. They write their handler against the underlying packages directly, exactly as in the [agent-framework break-glass sample](https://github.com/microsoft/agent-framework/blob/main/python/samples/04-hosting/foundry-hosted-agents/invocations/02_break_glass/main.py):

```python
from azure.ai.agentserver.core import AgentHost
from azure.ai.agentserver.invocations import InvocationHandler
from starlette.responses import JSONResponse

server = AgentHost()
invocations = InvocationHandler(server)

@invocations.invoke_handler
async def handle(request):
    data = await request.json()
    result = await my_graph.ainvoke({"messages": [...]}, config={...})
    return JSONResponse({"response": ...})

server.run()
```

Because the break-glass path is just the underlying packages, this design intentionally **does not** ship a `LangGraphAdapter` or `from_langgraph` factory. The two `*HostServer` classes plus direct underlying-package usage cover every scenario.

---

## 4. Internal design

### 4.1 Package layout

```
azure-ai-agentserver-langgraph/
├── azure/ai/agentserver/langgraph/
│   ├── __init__.py                 # ResponsesHostServer, InvocationsHostServer, ABCs
│   ├── _version.py
│   ├── py.typed
│   ├── _responses_host.py          # ResponsesHostServer
│   ├── _invocations_host.py        # InvocationsHostServer
│   └── _converters/
│       ├── __init__.py
│       ├── _request.py             # CreateResponse / invocation body → graph input
│       ├── _stream.py              # graph astream events → Responses event dicts
│       ├── _final.py               # graph final state → Responses output items + Invocations JSON
│       └── _utils.py               # message <-> ItemContent helpers
├── samples/
│   ├── responses/
│   │   ├── 01_basic/
│   │   ├── 02_streaming/
│   │   └── 03_workflow/
│   ├── invocations/
│   │   └── 01_basic/
│   └── multiprotocol_break_glass/  # uses underlying packages directly
├── tests/
│   ├── unit/
│   │   ├── test_request_converter.py
│   │   ├── test_stream_converter.py
│   │   └── test_final_converter.py
│   └── integration/
│       ├── test_responses_host.py     # Starlette TestClient against /responses
│       └── test_invocations_host.py   # Starlette TestClient against /invocations
├── pyproject.toml
└── README.md
```

The b17 trees for `tools/`, `checkpointer/`, and `models/response_event_generators/` are **not ported**. They are out of scope (§2).

### 4.2 `ResponsesHostServer` — wiring

```python
class ResponsesHostServer:
    def __init__(self, graph, *, options=None, provider=None, prefix="",
                 converter=None, **host_kwargs):
        self._graph = graph
        self._converter = converter or DefaultGraphResponsesConverter()
        self._server = AgentHost(**host_kwargs)
        self._handler = ResponseHandler(
            self._server, options=options, provider=provider, prefix=prefix,
        )

        @self._handler.create_handler
        async def _create(request, context, cancellation_signal):
            async for event in self._converter.run(
                graph=self._graph,
                request=request,
                context=context,
                cancellation_signal=cancellation_signal,
            ):
                yield event

    def run(self, host="0.0.0.0", port=None):
        self._server.run(host=host, port=port)
```

All routing, SSE encoding, lifecycle state machine, persistence, and graceful drain stay in `ResponseHandler`. This package contributes only the `(graph, request, context) → events` translation.

### 4.3 `InvocationsHostServer` — wiring

```python
class InvocationsHostServer:
    def __init__(self, graph, *, converter=None, **host_kwargs):
        self._graph = graph
        self._converter = converter or DefaultGraphInvocationsConverter()
        self._server = AgentHost(**host_kwargs)
        self._handler = InvocationHandler(self._server)

        @self._handler.invoke_handler
        async def _invoke(request):
            return await self._converter.run(graph=self._graph, request=request)

    def run(self, host="0.0.0.0", port=None):
        self._server.run(host=host, port=port)
```

Streaming over `/invocations` is decided by the converter based on the request body (`{"stream": true}` returns a `StreamingResponse`; otherwise `JSONResponse`). The `agent_session_id` is read off `request.state.session_id` (already populated by `InvocationHandler`) and **threaded into the `RunnableConfig.thread_id`** so a graph compiled with a checkpointer naturally continues the right conversation.

### 4.4 Converter ABCs

Two narrow ABCs, both async-iterable producers / awaitable producers:

```python
class GraphResponsesConverter(Protocol):
    async def run(
        self,
        *,
        graph: "CompiledStateGraph",
        request: CreateResponse,
        context: ResponseContext,
        cancellation_signal: asyncio.Event,
    ) -> AsyncIterator[dict[str, Any]]: ...


class GraphInvocationsConverter(Protocol):
    async def run(
        self,
        *,
        graph: "CompiledStateGraph",
        request: Request,
    ) -> Response: ...
```

Concrete defaults:

- `DefaultGraphResponsesConverter`
  1. Build `RunnableConfig` with `thread_id = context.conversation_id or context.previous_response_id or f"resp-{context.response_id}"`.
  2. Translate `request.input` (string or list of `InputParam`) into `{"messages": [...]}` using `langchain_core.messages` types. Identical logic to b17, minus the `AsyncOpenAI` history fallback.
  3. **Validate the graph state schema is `MessagesState`-compatible** (same `is_state_schema_valid` check as b17). If it is not, raise a `ValueError` at host construction time pointing the user at the `converter=` constructor argument. This preserves b17's contract: arbitrary LangGraph workflows / non-`MessagesState` graphs are supported, but only via a user-supplied `GraphResponsesConverter`.
  4. Construct a `ResponseEventStream(response_id=context.response_id, request=request)`.
  5. Emit `stream.emit_created()` / `emit_in_progress()`.
  6. **Stream mode follows b17**: if the request is streaming, iterate `graph.astream(input, config, stream_mode="messages")` and translate each delta to `OutputItemMessageBuilder` / `OutputItemFunctionCallBuilder` events. If non-streaming, drive the graph with `stream_mode="updates"` via `ainvoke` (i.e. `graph.ainvoke(...)` returns the aggregated update state) and synthesize the same event sequence in one shot.
  7. Emit `stream.emit_completed()` (or `emit_failed(...)` on error / `emit_cancelled()` if `cancellation_signal.is_set()`).

- `DefaultGraphInvocationsConverter`
  - **Request body schema follows the agent-framework break-glass sample verbatim**: `{"message": str | list[ChatMessage], "stream": bool = False}`.
  - Non-streaming: `result = await graph.ainvoke(...)`; respond with `{"response": <last AI message text>}`.
  - Streaming: SSE response yielding the text deltas from `graph.astream(..., stream_mode="messages")`.

Users override either ABC by passing `converter=` to the host.

### 4.5 Cancellation

- For `/responses`, the `cancellation_signal: asyncio.Event` provided by `ResponseHandler` is checked between yielded events; on set, the converter emits `response.cancelled` and stops iterating the graph.
- For `/invocations`, cancellation is handled at the Starlette layer (client disconnect); the converter does not register a custom cancellation channel in this scope.

### 4.6 Tracing

- `AgentHost` already wires OTel + Azure Monitor when `APPLICATIONINSIGHTS_CONNECTION_STRING` / `OTEL_EXPORTER_OTLP_ENDPOINT` is set. The hosts pass these via `**host_kwargs`; nothing else is needed.
- LangSmith / `AzureAIOpenTelemetryTracer` callback wiring is **postponed** (§2).

---

## 5. Examples

### 5.1 Basic Responses host

```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI
from azure.ai.agentserver.langgraph import ResponsesHostServer

graph = create_react_agent(AzureChatOpenAI(model="gpt-4o"), tools=[])

ResponsesHostServer(graph).run()
```

```bash
curl -X POST http://localhost:8088/responses \
  -H 'Content-Type: application/json' \
  -d '{"input": "Hello!"}'
```

### 5.2 Basic Invocations host

```python
from azure.ai.agentserver.langgraph import InvocationsHostServer

InvocationsHostServer(graph).run()
```

```bash
curl -X POST http://localhost:8088/invocations \
  -H 'Content-Type: application/json' \
  -d '{"message": "Hello!"}' -i
# Subsequent turn: include the x-agent-session-id header value as a query param.
curl -X POST 'http://localhost:8088/invocations?agent_session_id=<id>' \
  -H 'Content-Type: application/json' \
  -d '{"message": "And again?"}'
```

### 5.3 Custom Responses converter

```python
class MyConverter(GraphResponsesConverter):
    async def run(self, *, graph, request, context, cancellation_signal):
        ...

ResponsesHostServer(graph, converter=MyConverter()).run()
```

### 5.4 Break-glass (no `langgraph` package classes)

See §3.4. Users who want both protocols on one host or custom routing import directly from `azure.ai.agentserver.{core,responses,invocations}` and inline their `graph.ainvoke` / `graph.astream` calls inside their own handler. No additional support from this package is needed.

---

## 6. Implementation plan

> Each step is a self-contained PR on a new feature branch off `main`.

1. **Scaffold** the package layout in §4.1 with `pyproject.toml` dependencies on `azure-ai-agentserver-core`, `azure-ai-agentserver-responses`, `azure-ai-agentserver-invocations`, `langgraph>=0.6,<2`, `langchain-core>=0.3,<1`.
2. **Implement converters** (`_request.py`, `_stream.py`, `_final.py`, `_utils.py`).
3. **Implement `ResponsesHostServer`** (`_responses_host.py`) and end-to-end test it against `/responses` with Starlette `TestClient`.
4. **Implement `InvocationsHostServer`** (`_invocations_host.py`) and end-to-end test it against `/invocations`.
5. **Samples**: `responses/01_basic`, `responses/02_streaming`, `responses/03_workflow`, `invocations/01_basic`, `multiprotocol_break_glass`.
6. **README** modeled after the agent-framework foundry-hosted-agents README, with snippets for each sample.
7. **CI**: ensure pylint, mypy, pyright, sphinx, and tests-CI all PASS.

---

## 7. Acceptance criteria

- [ ] `ResponsesHostServer(graph).run()` boots a Hypercorn server exposing the full `/responses*` route set plus `/healthy`, with a working SSE round-trip against a trivial `create_react_agent` graph.
- [ ] `ResponsesHostServer` raises a clear `ValueError` at construction time when given a graph whose state schema is not `MessagesState`-compatible **and** no `converter=` was supplied.
- [ ] Custom `GraphResponsesConverter` is honored end-to-end (covers arbitrary workflows / non-`MessagesState` graphs).
- [ ] `InvocationsHostServer(graph).run()` boots a server exposing `/invocations*` plus `/healthy`, with both streaming and non-streaming round-trips against the same graph using the `{"message", "stream"}` body schema.
- [ ] `agent_session_id` continuity works for `/invocations` when the graph is compiled with a checkpointer (verified via `MemorySaver` in tests).
- [ ] `previous_response_id` / `conversation` continuity works for `/responses` via the in-memory `ResponseProviderProtocol`.
- [ ] Break-glass sample compiles and runs without importing anything from `azure.ai.agentserver.langgraph`.
- [ ] Pylint, MyPy, Pyright, Sphinx, Tests-CI all PASS.
