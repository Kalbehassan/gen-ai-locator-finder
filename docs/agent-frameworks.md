# Agent frameworks

## Core Stable

The repository has a deterministic ordered agent graph and explicit 15-step workflow. It does not depend on LangGraph or another framework at runtime.

## Optional Provider Integrations

LiteLLM and Google GenAI are explicit provider choices installed through the `cloud` extra.

## Experimental Demonstrations

LangChain, LangGraph, Guidance, Outlines, CrewAI, Agno, Pydantic AI, Google ADK, Semantic Kernel, DSPy and MCP have optional adapters. These adapters report package availability and must not be presented as validated autonomous execution.

Install examples:

```bash
python -m pip install -e ".[frameworks]"
```

These integrations require authorization and may have their own network, data-handling, and deployment constraints.
