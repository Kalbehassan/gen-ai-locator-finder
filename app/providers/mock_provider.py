# SPDX-License-Identifier: MIT
"""Offline deterministic mock LLM provider.

Core Stable: default provider for local and test execution.
This implementation does not pretend to perform real language understanding.
"""

from __future__ import annotations

from app.providers.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """Generate transparent deterministic mock suggestions."""

    name = "mock"

    async def generate(self, prompt: str, *, temperature: float = 0.0) -> str:
        """Return a deterministic locator hint derived from prompt terms."""
        del temperature
        lowered = prompt.lower()
        if "submit" in lowered or "save" in lowered:
            return "Prefer role=button plus visible text, then test_id or id."
        if "search" in lowered or "input" in lowered:
            return "Prefer accessible label or placeholder, then name or id."
        if "invoice" in lowered or "row" in lowered:
            return "Prefer text-adjacent structure, then table row ancestry and retry matching."
        return "Prefer test_id, id, accessible label, role, and visible text in that order."

    def capabilities(self) -> dict[str, object]:
        """Return transparent mock capability metadata."""
        return {"name": self.name, "offline": True, "real_llm": False, "paid_api": False}
