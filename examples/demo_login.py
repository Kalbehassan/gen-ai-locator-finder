# SPDX-License-Identifier: MIT
"""Demonstrate login-profile resolution without real credentials or live navigation."""

from app.agent.locator_agent import resolve_login_profile


def main() -> None:
    for name in ("standard_form", "email_password", "mfa_optional"):
        profile = resolve_login_profile(name)
        print(profile.model_dump(mode="json", exclude={"success_url_fragment", "success_text"}))


if __name__ == "__main__":
    main()
