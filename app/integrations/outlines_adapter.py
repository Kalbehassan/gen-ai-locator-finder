# SPDX-License-Identifier: MIT
"""Optional Outlines structured-output demonstration."""

from app.integrations.base_adapter import BaseFrameworkAdapter


class OutlinesAdapter(BaseFrameworkAdapter):
    name = "outlines"

    def __init__(self) -> None:
        try:
            import outlines  # type: ignore[import-not-found]

            self.available = True
        except ImportError:
            self.available = False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "available": self.available, "core_used": False}

    async def demonstrate(self, description: str) -> str:
        del description
        return (
            "Outlines unavailable"
            if not self.available
            else "Outlines structured output demonstration available"
        )
