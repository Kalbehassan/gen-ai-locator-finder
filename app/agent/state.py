# SPDX-License-Identifier: MIT
"""State definitions for the LangGraph UI locator discovery and healing agent.

Core Stable: this module defines serializable graph state and a public response
contract. Password values remain inside Pydantic ``SecretStr`` objects and are
never copied into workflow traces or response evidence.

Experimental: LangGraph execution is optional; the stable repository graph is
also available through ``app.agent.graph``.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.api.schemas import AgentState as PydanticAgentState
from app.browser.locator_registry import DOMNodeInfo, LocatorCandidate
from app.browser.playwright_client import (
    AuthenticationOutcome,
    LoginProfile,
    SnapshotPayload,
)


class AgentResponse(BaseModel):
    """Public response contract returned by discovery, healing, and analysis workflows."""

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(default=True)
    matched: bool = Field(default=False)
    best_locator: dict[str, Any] | None = Field(default=None)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    authentication: dict[str, Any] = Field(
        default_factory=lambda: {
            "status": "skipped",
            "sensitive_fields_redacted": True,
        }
    )
    warnings: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    suggested_tests: list[str] = Field(default_factory=list)
    exported_files: dict[str, str] = Field(default_factory=dict)
    workflow_trace: list[str] = Field(default_factory=list)


class LocatorAgentState(TypedDict, total=False):
    """Mutable graph state passed across LangGraph workflow nodes."""

    # Inputs: raw passwords must remain wrapped in SecretStr throughout the graph.
    url: str
    username: str | None
    password: SecretStr | None
    tenant: str | None
    login_profile: str | LoginProfile | None
    description: str
    failed_locator: dict[str, Any] | None
    snapshot_override: SnapshotPayload | None
    capture_screenshot: bool
    include_dynamic: bool
    export_format: Literal["json", "csv", "xlsx"] | None
    provider_name: str

    # Resolved and intermediate workflow state.
    resolved_profile: LoginProfile
    auth_outcome: AuthenticationOutcome
    snapshot: SnapshotPayload | None
    candidate_nodes: list[DOMNodeInfo]
    candidates: list[LocatorCandidate]
    verified_candidates: list[LocatorCandidate]
    selected_candidate: LocatorCandidate | None
    healing_attempts: int
    max_healing_attempts: int
    healed: bool
    warnings: list[str]
    suggested_tests: list[str]
    exported_files: dict[str, str]
    trace: list[str]

    # Final redacted public output.
    response: AgentResponse


def initial_locator_state(
    *,
    url: str,
    description: str,
    username: str | None = None,
    password: SecretStr | None = None,
    tenant: str | None = None,
    login_profile: str | LoginProfile | None = None,
    capture_screenshot: bool = False,
    include_dynamic: bool = True,
    provider_name: str = "mock",
    max_healing_attempts: int = 2,
) -> LocatorAgentState:
    """Create a complete initial graph state without exposing credential values."""
    return LocatorAgentState(
        url=url,
        username=username,
        password=password,
        tenant=tenant,
        login_profile=login_profile,
        description=description,
        failed_locator=None,
        snapshot_override=None,
        capture_screenshot=capture_screenshot,
        include_dynamic=include_dynamic,
        export_format=None,
        provider_name=provider_name,
        snapshot=None,
        candidate_nodes=[],
        candidates=[],
        verified_candidates=[],
        selected_candidate=None,
        healing_attempts=0,
        max_healing_attempts=max_healing_attempts,
        healed=False,
        warnings=[],
        suggested_tests=[],
        exported_files={},
        trace=[],
    )


def append_trace(state: LocatorAgentState, step: str) -> LocatorAgentState:
    """Append a workflow step name and return the same mutable state."""
    trace = state.setdefault("trace", [])
    if step not in trace:
        trace.append(step)
    return state


def advance(state: PydanticAgentState, step: str) -> PydanticAgentState:
    """Advance the legacy Pydantic in-process state to a named workflow step."""
    state.step = step
    return state


def complete(state: PydanticAgentState) -> PydanticAgentState:
    """Mark the legacy Pydantic workflow as completed."""
    state.step = "redact_response"
    state.completed_at = None
    return state
