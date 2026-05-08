"""Real-LLM Responses host using a Foundry-deployed Azure OpenAI model.

Boots ``ResponsesHostServer`` against a tiny ``create_react_agent`` graph
backed by a real Azure OpenAI chat model on Foundry.

Required environment variables::

    AZURE_AI_PROJECT_ENDPOINT  e.g. https://<acct>.services.ai.azure.com/api/projects/<proj>
    AZURE_AI_MODEL_DEPLOYMENT_NAME  e.g. gpt-4o   (defaults to "gpt-4o" when unset)
    PORT                       optional, defaults to 8188

Authentication uses ``DefaultAzureCredential`` (typically ``az login``)
against the ``https://ai.azure.com`` audience.  We target the project's
OpenAI v1 surface (``<endpoint>/openai/v1``) so this works for any model
deployed under the Foundry project.
"""
from __future__ import annotations

import os

from azure.identity import DefaultAzureCredential
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from azure.ai.agentserver.langgraph import LangGraphResponsesHostServer


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
    graph = create_react_agent(_build_chat_model(), tools=[])
    port = int(os.environ.get("PORT", "8088"))
    LangGraphResponsesHostServer(graph).run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
