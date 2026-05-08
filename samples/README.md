# Samples — azure-ai-agentserver-langgraph

| # | File | What it shows |
|---|------|---------------|
| 1 | [sample_01_responses_basic.py](sample_01_responses_basic.py) | Simplest case: host a `create_react_agent` graph as the Responses API. |
| 2 | [sample_02_responses_tools.py](sample_02_responses_tools.py) | Same graph + a `@tool` function. Intermediate tool calls and tool results are surfaced as `function_call` / `function_call_output` output items in both non-streaming and streaming modes. |
| 3 | [sample_03_invocations_basic.py](sample_03_invocations_basic.py) | Host the same graph as the Invocations API, with a `MemorySaver` checkpointer for multi-turn continuity via `agent_session_id`. |
| 4 | [sample_04_invocations_tools.py](sample_04_invocations_tools.py) | Variant of #3 with a local `@tool` function — the agent runs a tool round-trip server-side and returns the final assistant text. Streaming returns per-token text deltas. |
| 5 | [sample_05_workflow_all_in_one.py](sample_05_workflow_all_in_one.py) | All-in-one: a custom multi-node `StateGraph` (plan → tools → synthesize) with two tools, hosted as **both** the Responses API and the Invocations API on the same port via the `app=` parameter. |

## Setup

From the sample root:

```bash
# 1. (Recommended) create and activate a virtual environment
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# 2. Install this package and the sample dependencies
pip install -r requirements.txt

# 3. Copy the example env file and fill in your values
cp .env.example .env
# Windows (PowerShell):
#   Copy-Item .env.example .env
```

`requirements.txt` installs the local `azure-ai-agentserver-langgraph`
package (via `-e ..`) together with `langchain`, `langchain-openai`,
`langgraph`, and `python-dotenv`. The sibling `azure-ai-agentserver-*`
packages are pulled from PyPI as transitive dependencies — you do not need
to clone or install them manually.

## Configuration

Edit the `.env` you just created and set at minimum
`AZURE_AI_PROJECT_ENDPOINT`. `AZURE_AI_MODEL_DEPLOYMENT_NAME` (defaults to
`gpt-4o`) and `PORT` (defaults to `8088`) are optional. See
[.env.example](.env.example) for the full list.

Each sample calls `load_dotenv()`, which searches upward from the script
for a `.env` file and does **not** override values already set in your
shell — real environment variables take precedence.

Authentication uses `DefaultAzureCredential` against the
`https://ai.azure.com` audience — `az login` is the simplest setup.

## Running a sample

From the sample root, after the setup above:

```bash
python sample_01_responses_basic.py
```

Open Agent Inspector with the corresponding API and send a message to trigger the agent.

