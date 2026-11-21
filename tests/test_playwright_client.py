# SPDX-License-Identifier: MIT

from pathlib import Path

from app.browser.playwright_client import PlaywrightClient


def test_client_initialization(tmp_path: Path) -> None:
    client = PlaywrightClient(headless=True, timeout_ms=15000, screenshot_dir=tmp_path)
    assert client.headless is True
    assert client.capture_screenshots is False


def test_client_rejects_invalid_url() -> None:
    client = PlaywrightClient()
    import asyncio

    async def run() -> None:
        client._context = object()  # type: ignore[assignment]
        try:
            await client.navigate("javascript:alert(1)")
        except ValueError:
            return
        raise AssertionError("invalid URL was accepted")

    asyncio.run(run())
