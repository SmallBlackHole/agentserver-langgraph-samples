# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
"""Azure AI Agent Server adapter for LangGraph.

Host a LangGraph :class:`~langgraph.graph.state.CompiledStateGraph` as the
Azure AI Responses API or Invocations API on top of
:mod:`azure.ai.agentserver.core`.

Quick start (Responses API)::

    from azure.ai.agentserver.langgraph import ResponsesHostServer

    ResponsesHostServer(my_compiled_graph).run()

Quick start (Invocations API)::

    from azure.ai.agentserver.langgraph import InvocationsHostServer

    InvocationsHostServer(my_compiled_graph).run()

For multi-protocol or custom-route scenarios, drop down to
:class:`azure.ai.agentserver.responses.ResponsesAgentServerHost` and
:class:`azure.ai.agentserver.invocations.InvocationAgentServerHost`
directly and write your own ``@response_handler`` / ``@invoke_handler``.
"""
__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from ._invocations_host import LangGraphInvocationsHostServer
from ._responses_host import LangGraphResponsesHostServer
from ._version import VERSION

__all__ = [
    "LangGraphInvocationsHostServer",
    "LangGraphResponsesHostServer",
]
__version__ = VERSION
