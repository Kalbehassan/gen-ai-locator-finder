# SPDX-License-Identifier: MIT
"""Optional DSPy demonstration adapter."""

from app.integrations.base_adapter import BaseFrameworkAdapter


class DSPyAdapter(BaseFrameworkAdapter):
    name = "dspy"

    def __init__(self) -> None:
        try:
            import dspy  # type: ignore[import-not-found]

            self.available = True
        except ImportError:
            self.available = False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "available": self.available, "core_used": False}

    async def demonstrate(self, description: str) -> str:
        del description
        return (
            "DSPy unavailable"
            if not self.available
            else "DSPy prompt optimization demonstration available"
        )
