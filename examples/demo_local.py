# SPDX-License-Identifier: MIT
"""Local demo using only rule-based ranking and mock provider behavior."""

from app.agent.locator_agent import LocatorAgent
from app.api.schemas import LocatorRequest
from app.browser.models import CandidateElement


def main() -> None:
    request = LocatorRequest(
        url="https://example.invalid/local-demo",
        description="Find the submit button",
        login_profile="standard_form",
    )
    agent = LocatorAgent()
    state = agent.initialize(request)
    elements = [
        CandidateElement(
            element_id="save",
            tag="button",
            text="Save",
            role="button",
            attributes={"type": "submit"},
        )
    ]
    candidates = agent.discover_candidates(elements, request.description)
    state.result.matched = bool(candidates)
    state.result.success = bool(candidates)
    state.result.best_locator = candidates[0] if candidates else None
    state.result.alternatives = candidates[1:]
    print(agent.response(state).model_dump(mode="json", exclude={"authentication"}))


if __name__ == "__main__":
    main()
