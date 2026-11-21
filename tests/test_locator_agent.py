# SPDX-License-Identifier: MIT

from app.agent.locator_agent import LocatorAgent, resolve_login_profile
from app.api.schemas import LocatorRequest
from app.browser.models import CandidateElement


def test_profile_resolution() -> None:
    profile = resolve_login_profile("email_password")
    assert profile.username_selector


def test_agent_candidate_discovery() -> None:
    request = LocatorRequest(url="https://example.invalid", description="Find the save button")
    agent = LocatorAgent()
    state = agent.initialize(request)
    element = CandidateElement(
        element_id="save",
        tag="button",
        text="Save",
        role="button",
        attributes={"id": "save", "data-testid": "save-button"},
    )
    candidates = agent.discover_candidates([element], request.description)
    assert candidates
    assert candidates[0].strategy in {"id", "test_id", "role", "text", "css"}
    assert state.step == "validate_request"
