"""Real-LLM Responses host with a local tool — verifies function-call rendering."""
from __future__ import annotations

import os
from random import randint
from typing import Annotated

from azure.identity import DefaultAzureCredential
from langchain_core.tools import tool
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


@tool
def get_weather(location: Annotated[str, "City and country, e.g. 'Seattle, US'."]) -> str:
    """Return a fake weather snapshot for the given location."""
    conditions = ["sunny", "cloudy", "rainy", "stormy"]
    return f"The weather in {location} is {conditions[randint(0, 3)]} with a high of {randint(10, 30)}C."


def main() -> None:
    graph = create_react_agent(_build_chat_model(), tools=[get_weather])
    port = int(os.environ.get("PORT", "8190"))
    LangGraphResponsesHostServer(graph).run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
