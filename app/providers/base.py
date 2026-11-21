# SPDX-License-Identifier: MIT
"""LLM provider abstraction.

Core Stable: provider capability reporting and prompt contract.
Optional: cloud providers implement this interface without changing agent code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ProviderUnavailableError(RuntimeError):
    """Raised when an explicitly selected provider is unavailable."""


class BaseLLMProvider(ABC):
    """Minimal text generation interface used by locator agent demos."""

    name: str

    @abstractmethod
    async def generate(self, prompt: str, *, temperature: float = 0.0) -> str:
        """Generate provider text or raise a provider-specific error."""

    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        """Describe provider availability without exposing credentials."""
