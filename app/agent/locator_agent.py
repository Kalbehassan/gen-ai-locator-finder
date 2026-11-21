# SPDX-License-Identifier: MIT
"""High-level LocatorAgent facade orchestrating discovery, healing, and snapshot analysis.

Core Stable: it composes graph runtime, browser client, registry, and redacted response state.
Optional Provider Integrations: vector stores and exporters are injected dependencies.
Experimental: provider selection and graph execution are demonstration hooks.
Future Roadmap: persistent sessions and checkpointed workflows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, cast

from pydantic import SecretStr

from app.agent.graph import LocatorGraphRuntime, build_locator_graph
from app.agent.state import AgentResponse, LocatorAgentState
from app.api.schemas import (
    AgentResponse as LegacyAgentResponse,
)
from app.api.schemas import (
    AgentState,
    AuthenticationResult,
    LocatorRequest,
)
from app.browser.locator_registry import DOMNodeInfo, LocatorRegistry
from app.browser.models import CandidateElement
from app.browser.playwright_client import (
    LoginProfile,
    PlaywrightClient,
    SnapshotPayload,
    resolve_login_profile,
)


@dataclass
class LocatorAgent:
    """Entry-point service for locating, verifying, analyzing, and healing UI locators."""

    browser_client: PlaywrightClient | None = None
    registry: LocatorRegistry = field(default_factory=LocatorRegistry)
    vector_store: Any = None
    exporter: Any = None
    provider_name: str = "mock"
    _graph: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """Build an injected graph runtime and compiled LangGraph/local fallback."""
        runtime = LocatorGraphRuntime(
            browser_client=self.browser_client,
            registry=self.registry,
            vector_store=self.vector_store,
            exporter=self.exporter,
        )
        self._graph = build_locator_graph(runtime)

    async def discover(
        self,
        *,
        url: str,
        description: str,
        username: str | None = None,
        password: SecretStr | str | None = None,
        tenant: str | None = None,
        login_profile: str | LoginProfile | None = None,
        capture_screenshot: bool = False,
        include_dynamic: bool = True,
        export_format: Literal["json", "csv", "xlsx"] | None = None,
    ) -> AgentResponse:
        """Run full navigation, authentication, snapshot capture, ranking, and verification."""
        secret_pw = (
            password
            if isinstance(password, SecretStr)
            else (SecretStr(password) if password else None)
        )
        initial_state: LocatorAgentState = {
            "url": url,
            "username": username,
            "password": secret_pw,
            "tenant": tenant,
            "login_profile": login_profile,
            "description": description,
            "capture_screenshot": capture_screenshot,
            "include_dynamic": include_dynamic,
            "export_format": export_format,
            "provider_name": self.provider_name,
        }
        final_state = cast(LocatorAgentState, await self._graph.ainvoke(initial_state))
        return final_state["response"]

    async def heal(
        self,
        *,
        url: str,
        description: str,
        failed_locator: dict[str, Any],
        username: str | None = None,
        password: SecretStr | str | None = None,
        tenant: str | None = None,
        login_profile: str | LoginProfile | None = None,
        snapshot: SnapshotPayload | None = None,
    ) -> AgentResponse:
        """Heal a broken locator using live/snapshot context and fallback strategies."""
        secret_pw = (
            password
            if isinstance(password, SecretStr)
            else (SecretStr(password) if password else None)
        )
        initial_state: LocatorAgentState = {
            "url": url,
            "username": username,
            "password": secret_pw,
            "tenant": tenant,
            "login_profile": login_profile,
            "description": description,
            "failed_locator": failed_locator,
            "snapshot_override": snapshot,
            "capture_screenshot": False,
            "include_dynamic": True,
            "provider_name": self.provider_name,
        }
        final_state = cast(LocatorAgentState, await self._graph.ainvoke(initial_state))
        return final_state["response"]

    async def analyze_snapshot(
        self,
        *,
        snapshot: SnapshotPayload,
        description: str,
        include_dynamic: bool = True,
        export_format: Literal["json", "csv", "xlsx"] | None = None,
    ) -> AgentResponse:
        """Analyze an existing SnapshotPayload without launching a live browser."""
        initial_state: LocatorAgentState = {
            "url": snapshot.url,
            "description": description,
            "snapshot_override": snapshot,
            "capture_screenshot": False,
            "include_dynamic": include_dynamic,
            "export_format": export_format,
            "provider_name": self.provider_name,
        }
        final_state = cast(LocatorAgentState, await self._graph.ainvoke(initial_state))
        return final_state["response"]

    def initialize(self, request: LocatorRequest) -> AgentState:
        """Initialize the legacy Pydantic workflow state used by unit tests."""
        from app.api.schemas import LoginProfile as ApiLoginProfile

        profile = ApiLoginProfile(name=request.login_profile)
        return AgentState(
            request=request,
            profile=profile,
            authentication=AuthenticationResult(status="skipped"),
            step="validate_request",
        )

    def discover_candidates(
        self,
        elements: list[CandidateElement],
        description: str,
    ) -> list[Any]:
        """Generate rich locator candidates for a legacy candidate-element test/list."""
        nodes: list[DOMNodeInfo] = []
        for element in elements:
            attributes: dict[str, object] = dict(element.attributes)
            test_id_value = attributes.get("data-testid")
            test_id = test_id_value if isinstance(test_id_value, str) else None
            nodes.append(
                DOMNodeInfo(
                    tag=element.tag,
                    element_id=element.element_id,
                    classes=[],
                    role=element.role,
                    accessible_name=element.accessible_name,
                    text=element.text,
                    test_id=test_id,
                    xpath=element.dom_path,
                    css=None,
                    bbox=[
                        element.bbox.x,
                        element.bbox.y,
                        element.bbox.width,
                        element.bbox.height,
                    ]
                    if element.bbox is not None
                    else [0.0, 0.0, 0.0, 0.0],
                    visible=True,
                    attributes=attributes,
                )
            )
        return self.registry.generate_candidates(nodes, description)

    def response(self, state: AgentState) -> LegacyAgentResponse:
        """Build the legacy API response shape from Pydantic workflow state."""
        state.completed_at = datetime.now(UTC)
        result = state.result
        return LegacyAgentResponse(
            success=result.success,
            matched=result.matched,
            best_locator=result.best_locator,
            alternatives=result.alternatives,
            authentication=state.authentication,
            warnings=state.warnings,
            evidence=result.evidence,
            suggested_tests=result.suggested_tests,
        )


__all__ = [
    "LocatorAgent",
    "resolve_login_profile",
]
