# SPDX-License-Identifier: MIT
"""Optional Pydantic AI demonstration adapter."""

from app.integrations.base_adapter import BaseFrameworkAdapter


class PydanticAIAdapter(BaseFrameworkAdapter):
    name = "pydantic-ai"

    def __init__(self) -> None:
        try:
            import pydantic_ai  # type: ignore[import-not-found]

            self.available = True
        except ImportError:
            self.available = False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "available": self.available, "core_used": False}

    async def demonstrate(self, description: str) -> str:
        del description
        return (
            "Pydantic AI unavailable"
            if not self.available
            else "Pydantic AI demonstration available"
        )
