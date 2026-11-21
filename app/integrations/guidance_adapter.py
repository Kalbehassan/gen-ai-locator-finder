# SPDX-License-Identifier: MIT
"""Optional Guidance structured-generation demonstration."""

from app.integrations.base_adapter import BaseFrameworkAdapter


class GuidanceAdapter(BaseFrameworkAdapter):
    name = "guidance"

    def __init__(self) -> None:
        try:
            import guidance  # type: ignore[import-not-found]

            self.available = True
        except ImportError:
            self.available = False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "available": self.available, "core_used": False}

    async def demonstrate(self, description: str) -> str:
        del description
        return (
            "Guidance unavailable"
            if not self.available
            else "Guidance structured prompt demonstration available"
        )
