# SPDX-License-Identifier: MIT
"""Base contract for optional agent-framework demonstrations."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseFrameworkAdapter(ABC):
    """Adapter with transparent availability and capability reporting."""

    name: str

    @abstractmethod
    def capabilities(self) -> dict[str, object]:
        """Return framework availability and integration status."""

    @abstractmethod
    async def demonstrate(self, description: str) -> str:
        """Return a safe demonstration result or a clear unavailability message."""
