# Samples — azure-ai-agentserver-langgraph

| # | File | What it shows |
|---|------|---------------|
| 1 | sample_01_responses_basic.py | Simplest case: host a `create_react_agent` graph as the Responses API. |
| 2 | sample_02_responses_tools.py | Same graph + a `@tool` function. Shows that intermediate tool calls and tool results are surfaced as `function_call` / `function_call_output` output items in both non-streaming and streaming modes. |
| 2c | sample_02_client_demo.py | Probes the running sample 2 server, prints both non-streaming `output` items and the streaming SSE event timeline. Run after `sample_02_responses_tools.py`. |
| 3 | sample_03_invocations_basic.py | Host the same graph as the Invocations API, with a `MemorySaver` checkpointer for multi-turn continuity via `agent_session_id`. |
| 3t | sample_03_invocations_tools.py | Variant of #3 with a local `@tool` function — the agent runs a tool round-trip server-side and returns the final assistant text. Streaming returns per-token text deltas. |
| 4 | sample_04_break_glass_multiprotocol.py | "Break-glass": drop down to `ResponsesAgentServerHost` + `InvocationAgentServerHost` and write your own handlers when you need full control. |
| 5 | sample_05_workflow_all_in_one.py | All-in-one: a custom multi-node `StateGraph` (plan → tools → synthesize) with two tools, hosted as **both** the Responses API and the Invocations API on the same port via the `app=` parameter. |

Set `AZURE_AI_PROJECT_ENDPOINT` (and optionally `AZURE_AI_MODEL_DEPLOYMENT_NAME`,
defaults to `gpt-4o`) before running. The simplest workflow is to copy
[.env.example](.env.example) to `.env` next to it and fill in the values — every
sample auto-loads `samples/.env` via `python-dotenv`. You can still override
any value from the shell environment (real env vars take precedence over the
file). Authentication uses `DefaultAzureCredential` against the
`https://ai.azure.com` audience — `az login` is the simplest setup.

Set `AZURE_AI_PROJECT_ENDPOINT` (and optionally `AZURE_AI_MODEL_DEPLOYMENT_NAME`,
defaults to `gpt-4o`) before running. The simplest workflow is to copy
[.env.example](.env.example) to `.env` next to it and fill in the values — every
sample auto-loads `samples/.env` via `python-dotenv`. You can still override
any value from the shell environment (real env vars take precedence over the
file). Authentication uses `DefaultAzureCredential` against the
`https://ai.azure.com` audience — `az login` is the simplest setup.
