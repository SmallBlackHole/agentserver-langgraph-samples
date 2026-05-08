"""Real-LLM Invocations host using a Foundry-deployed Azure OpenAI model."""
from __future__ import annotations

import os

from azure.identity import DefaultAzureCredential
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from azure.ai.agentserver.langgraph import LangGraphInvocationsHostServer


_AAD_SCOPE = "https://ai.azure.com/.default"


def _build_chat_model() -> ChatOpenAI:
    project_endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"].rstrip("/")
    deployment = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")
    credential = DefaultAzureCredential()
    token = credential.get_token(_AAD_SCOPE).token
    return ChatOpenAI(
        model=deployment,
        api_key=token,  # type: ignore[arg-type]
        base_url=f"{project_endpoint}/openai/v1",
    )


def main() -> None:
    graph = create_react_agent(_build_chat_model(), tools=[], checkpointer=MemorySaver())
    port = int(os.environ.get("PORT", "8189"))
    LangGraphInvocationsHostServer(graph).run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
