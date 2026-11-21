# SPDX-License-Identifier: MIT
"""Optional Google GenAI provider adapter.

Requires authorization and the `cloud` extra. It is never selected by default.
"""

from __future__ import annotations

from app.providers.base import BaseLLMProvider, ProviderUnavailableError


class GenAIProvider(BaseLLMProvider):
    """Call Gemini through google-genai when explicitly selected."""

    name = "genai"

    def __init__(self, model: str = "gemini-2.5-flash", api_key: str | None = None) -> None:
        self.model = model
        try:
            from google import genai  # type: ignore[import-not-found]

            self._client = genai.Client(api_key=api_key)
        except ImportError as exc:
            raise ProviderUnavailableError("Install the 'cloud' extra to use Google GenAI") from exc

    async def generate(self, prompt: str, *, temperature: float = 0.0) -> str:
        """Generate text using the configured Gemini model."""
        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config={"temperature": temperature},
        )
        return str(getattr(response, "text", "") or "")

    def capabilities(self) -> dict[str, object]:
        """Report provider capabilities without leaking API credentials."""
        return {"name": self.name, "offline": False, "real_llm": True, "paid_api_possible": True}
