# SPDX-License-Identifier: MIT
"""Optional MCP server integration demonstration.

This module reports availability and exposes only non-secret capability metadata.
"""

from app.integrations.base_adapter import BaseFrameworkAdapter


class MCPServerAdapter(BaseFrameworkAdapter):
    name = "mcp"

    def __init__(self) -> None:
        try:
            import mcp  # type: ignore[import-not-found]

            self.available = True
        except ImportError:
            self.available = False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "available": self.available, "core_used": False}

    async def demonstrate(self, description: str) -> str:
        del description
        return (
            "MCP unavailable" if not self.available else "MCP tool surface demonstration available"
        )
