# SPDX-License-Identifier: MIT
"""Optional LangChain demonstration adapter.
Requires the `frameworks` extra; never used by the stable agent path."""

from app.integrations.base_adapter import BaseFrameworkAdapter


class LangChainAdapter(BaseFrameworkAdapter):
    name = "langchain"

    def __init__(self) -> None:
        try:
            import langchain  # type: ignore[import-not-found]

            self.available = True
        except ImportError:
            self.available = False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "available": self.available, "core_used": False}

    async def demonstrate(self, description: str) -> str:
        if not self.available:
            return "Install the 'frameworks' extra to enable LangChain demonstrations"
        return f"LangChain demonstration requested for: {description[:120]}"
