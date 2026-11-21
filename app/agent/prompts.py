# SPDX-License-Identifier: MIT
"""Prompt templates and workflow guidance.

Core Stable: prompt templates contain no credentials or target content.
Optional: cloud providers can use these templates after explicit selection.
"""

from __future__ import annotations

SYSTEM_PROMPT = """You assist UI test automation engineers in choosing resilient Playwright locators.
Prefer test IDs, unique ids, accessible names and roles over brittle generated XPath.
Never return credentials, secrets, or raw page HTML. Explain uncertainty and verification risks.
"""

WORKFLOW_STEPS = (
    "validate_request",
    "resolve_login_profile",
    "launch_browser",
    "navigate",
    "authenticate",
    "capture_context",
    "extract_candidates",
    "generate_static",
    "generate_dynamic",
    "rank_candidates",
    "verify_live",
    "heal_failed",
    "explain_evidence",
    "export_optional",
    "redact_response",
)


def locator_prompt(description: str, visible_text: str) -> str:
    """Create a bounded prompt that excludes credential fields by contract."""
    safe_description = " ".join(description.split())[:1000]
    safe_text = " ".join(visible_text.split())[:3000]
    return f"{SYSTEM_PROMPT}\nTarget description: {safe_description}\nVisible text: {safe_text}"
