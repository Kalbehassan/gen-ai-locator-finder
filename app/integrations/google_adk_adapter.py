# SPDX-License-Identifier: MIT
"""Optional Google ADK demonstration adapter."""

from app.integrations.base_adapter import BaseFrameworkAdapter


class GoogleADKAdapter(BaseFrameworkAdapter):
    name = "google-adk"

    def __init__(self) -> None:
        try:
            import google.adk  # type: ignore[import-not-found]

            self.available = True
        except ImportError:
            self.available = False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "available": self.available, "core_used": False}

    async def demonstrate(self, description: str) -> str:
        del description
        return (
            "Google ADK unavailable" if not self.available else "Google ADK demonstration available"
        )
