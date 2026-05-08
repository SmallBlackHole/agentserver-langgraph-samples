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

## Contributing

This project welcomes contributions and suggestions. Most contributions
require you to agree to a Contributor License Agreement (CLA) declaring
that you have the right to, and actually do, grant us the rights to use
your contribution. For details, visit https://cla.microsoft.com.
