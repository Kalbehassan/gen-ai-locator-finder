# SPDX-License-Identifier: MIT
"""Optional CrewAI demonstration adapter."""

from app.integrations.base_adapter import BaseFrameworkAdapter


class CrewAIAdapter(BaseFrameworkAdapter):
    name = "crewai"

    def __init__(self) -> None:
        try:
            import crewai  # type: ignore[import-not-found]

            self.available = True
        except ImportError:
            self.available = False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "available": self.available, "core_used": False}

    async def demonstrate(self, description: str) -> str:
        del description
        return (
            "CrewAI unavailable"
            if not self.available
            else "CrewAI locator workflow demonstration available"
        )
