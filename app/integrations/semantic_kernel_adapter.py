# SPDX-License-Identifier: MIT
"""Optional Semantic Kernel demonstration adapter."""

from app.integrations.base_adapter import BaseFrameworkAdapter


class SemanticKernelAdapter(BaseFrameworkAdapter):
    name = "semantic-kernel"

    def __init__(self) -> None:
        try:
            import semantic_kernel  # type: ignore[import-not-found]

            self.available = True
        except ImportError:
            self.available = False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "available": self.available, "core_used": False}

    async def demonstrate(self, description: str) -> str:
        del description
        return (
            "Semantic Kernel unavailable"
            if not self.available
            else "Semantic Kernel demonstration available"
        )
