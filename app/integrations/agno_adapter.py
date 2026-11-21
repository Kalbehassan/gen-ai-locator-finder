# SPDX-License-Identifier: MIT
"""Optional Agno demonstration adapter."""

from app.integrations.base_adapter import BaseFrameworkAdapter


class AgnoAdapter(BaseFrameworkAdapter):
    name = "agno"

    def __init__(self) -> None:
        try:
            import agno  # type: ignore[import-not-found]

            self.available = True
        except ImportError:
            self.available = False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "available": self.available, "core_used": False}

    async def demonstrate(self, description: str) -> str:
        del description
        return "Agno unavailable" if not self.available else "Agno agent demonstration available"
