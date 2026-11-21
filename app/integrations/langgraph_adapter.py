# SPDX-License-Identifier: MIT
"""Optional LangGraph adapter demonstration."""

from app.integrations.base_adapter import BaseFrameworkAdapter


class LangGraphAdapter(BaseFrameworkAdapter):
    name = "langgraph"

    def __init__(self) -> None:
        try:
            import langgraph  # type: ignore[import-not-found]

            self.available = True
        except ImportError:
            self.available = False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "available": self.available, "core_used": False}

    async def demonstrate(self, description: str) -> str:
        if not self.available:
            return "Install the 'frameworks' extra to enable LangGraph demonstrations"
        return f"LangGraph graph demo for: {description[:120]}"
