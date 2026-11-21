# SPDX-License-Identifier: MIT
"""Demo HTTP client for an authorized local target.

Never include real credentials in source control or sample command output.
"""

from __future__ import annotations

import os

import httpx


def main() -> None:
    url = os.getenv("LOCATOR_APP_URL")
    username = os.getenv("LOCATOR_APP_USERNAME")
    password = os.getenv("LOCATOR_APP_PASSWORD")
    payload: dict[str, object] = {
        "url": url or "https://example.invalid",
        "description": "Find the submit button",
        "login_profile": "standard_form",
    }
    if username:
        payload["username"] = username
    if password:
        payload["password"] = password

    response = httpx.post("http://127.0.0.1:8000/locate", json=payload, timeout=30)
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()
