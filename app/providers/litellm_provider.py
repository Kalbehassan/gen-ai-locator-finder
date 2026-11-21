# SPDX-License-Identifier: MIT
"""Optional LiteLLM cloud provider adapter.

Not imported by the default local path. Requires the `cloud` extra and user authorization.
"""

from __future__ import annotations

from app.providers.base import BaseLLMProvider, ProviderUnavailableError


class LiteLLMProvider(BaseLLMProvider):
    """Call LiteLLM only after an optional package is available."""

    name = "litellm"

    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key
        try:
            import litellm  # type: ignore[import-not-found]

            self._litellm = litellm
        except ImportError as exc:
            raise ProviderUnavailableError("Install the 'cloud' extra to use LiteLLM") from exc

    async def generate(self, prompt: str, *, temperature: float = 0.0) -> str:
        """Generate text using LiteLLM's async completion API."""
        response = await self._litellm.acompletion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            api_key=self.api_key,
        )
        return str(response.choices[0].message.content or "")

    def capabilities(self) -> dict[str, object]:
        """Report a real optional cloud capability without credential metadata."""
        return {"name": self.name, "offline": False, "real_llm": True, "paid_api_possible": True}
