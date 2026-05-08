# Release History

## 1.0.0b1 (Unreleased)

### Features Added

- Initial release of the rewritten `azure-ai-agentserver-langgraph` package.
- `ResponsesHostServer(graph)` — host a LangGraph `CompiledStateGraph` as the Azure AI Responses API.
- `InvocationsHostServer(graph)` — host a LangGraph `CompiledStateGraph` as the Azure AI Invocations API.
- Default request/response converters supporting `MessagesState`-compatible graphs with token-by-token SSE streaming and non-streaming responses.
- Custom converter override via the `converter=` constructor argument.

### Breaking Changes

- This is a clean rewrite. No public API from `1.0.0b17` is preserved.
