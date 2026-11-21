# SPDX-License-Identifier: MIT
"""LangGraph workflow for UI locator discovery, verification, and healing.

Core Stable: deterministic workflow nodes and a local ordered fallback graph.
Optional Provider Integrations: LangGraph and cloud providers are dependency-gated.
Experimental: vector-similarity hints and LLM-generated candidates.
Future Roadmap: persistent graph checkpointing and learned healing policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, cast

from app.agent.state import AgentResponse, LocatorAgentState
from app.browser.locator_registry import (
    LocatorCandidate,
    LocatorRegistry,
)
from app.browser.playwright_client import (
    AuthenticationOutcome,
    PlaywrightClient,
    SnapshotPayload,
    resolve_login_profile,
)
from app.security.redaction import redact_payload, redact_text


def _collect_extra_secrets(state: LocatorAgentState) -> list[str]:
    """Collect explicit password values only for in-process redaction."""
    password = state.get("password")
    if password is None:
        return []
    secret = password.get_secret_value()
    return [secret] if secret else []


def _append_trace(state: LocatorAgentState, step: str) -> list[str]:
    """Append a workflow trace step once, preserving existing trace order."""
    trace = list(state.get("trace") or [])
    if step not in trace:
        trace.append(step)
    return trace


def _suggested_tests(candidate: LocatorCandidate | None, description: str) -> list[str]:
    """Build safe Playwright assertions for a matched or missing candidate."""
    safe_description = redact_text(description).replace('"', "'")
    if candidate is None:
        return [
            f"# Add a Playwright assertion once the locator is verified: {safe_description}",
        ]
    expression = candidate.playwright_expr
    return [
        f'{expression}.wait_for(state="visible")',
        f"assert await {expression}.count() == 1",
    ]


@dataclass
class LocatorGraphRuntime:
    """Dependencies injected into discovery graph nodes."""

    browser_client: PlaywrightClient | None = None
    registry: LocatorRegistry = field(default_factory=LocatorRegistry)
    vector_store: Any = None
    exporter: Any = None

    async def validate_request(self, state: LocatorAgentState) -> dict[str, Any]:
        """Validate URL/description and initialize bounded workflow state."""
        warnings = list(state.get("warnings") or [])
        url = (state.get("url") or "").strip()
        description = (state.get("description") or "").strip()

        if not description:
            warnings.append("Element description was empty; broad interactive matching is used.")
            description = "Locate target UI element"
        if not url and state.get("snapshot_override") is None:
            warnings.append("No URL or snapshot was provided; offline snapshot mode is used.")

        return {
            "url": url,
            "description": description,
            "warnings": warnings,
            "healing_attempts": int(state.get("healing_attempts") or 0),
            "max_healing_attempts": int(state.get("max_healing_attempts") or 2),
            "healed": False,
            "trace": _append_trace(state, "01_validate_request"),
        }

    async def resolve_profile(self, state: LocatorAgentState) -> dict[str, Any]:
        """Resolve a named or custom login profile."""
        profile = resolve_login_profile(state.get("login_profile"))
        return {
            "resolved_profile": profile,
            "trace": _append_trace(state, f"02_resolve_profile:{profile.profile_name}"),
        }

    async def capture_context(self, state: LocatorAgentState) -> dict[str, Any]:
        """Capture a supplied snapshot or launch Playwright for live capture."""
        extra_secrets = _collect_extra_secrets(state)
        warnings = list(state.get("warnings") or [])
        override = state.get("snapshot_override")
        profile = state.get("resolved_profile", resolve_login_profile(None))

        if isinstance(override, SnapshotPayload):
            auth = AuthenticationOutcome(
                status="skipped",
                profile_name=profile.profile_name,
                sensitive_fields_redacted=True,
                message="Snapshot supplied directly; live authentication skipped.",
            )
            return {
                "auth_outcome": auth,
                "snapshot": override,
                "trace": _append_trace(state, "03_capture_context:snapshot_override"),
            }

        url = state.get("url") or ""
        client = self.browser_client or PlaywrightClient(
            capture_screenshots=bool(state.get("capture_screenshot", False))
        )
        auth = AuthenticationOutcome(
            status="skipped",
            profile_name=profile.profile_name,
            sensitive_fields_redacted=True,
            message="No target URL provided.",
        )
        snapshot: SnapshotPayload | None = None

        if url:
            try:
                async with client:
                    await client.navigate(url)
                    auth = await client.authenticate(
                        username=state.get("username"),
                        password=state.get("password"),
                        tenant=state.get("tenant"),
                        profile=profile,
                    )
                    if auth.status == "failed":
                        warnings.append(redact_text(auth.message, extra_secrets=extra_secrets))
                    snapshot = await client.capture_snapshot(
                        include_screenshot=bool(state.get("capture_screenshot", False)),
                        extra_secrets=extra_secrets,
                    )
            except Exception as exc:
                safe_message = redact_text(str(exc), extra_secrets=extra_secrets)
                warnings.append(f"Browser capture encountered an error: {safe_message}")
                auth = AuthenticationOutcome(
                    status="failed",
                    profile_name=profile.profile_name,
                    sensitive_fields_redacted=True,
                    message=safe_message,
                )

        return {
            "auth_outcome": auth,
            "snapshot": snapshot,
            "warnings": warnings,
            "trace": _append_trace(state, "03_capture_context"),
        }

    async def extract_and_generate(self, state: LocatorAgentState) -> dict[str, Any]:
        """Extract normalized nodes and generate static/dynamic candidates."""
        snapshot = state.get("snapshot")
        nodes = list(snapshot.nodes) if snapshot and snapshot.nodes else []
        description = state.get("description") or ""

        embedding_hints: dict[int, float] | None = None
        if self.vector_store is not None:
            try:
                score_nodes = getattr(self.vector_store, "score_nodes", None)
                if callable(score_nodes):
                    embedding_hints = score_nodes(description, nodes)
            except Exception:
                embedding_hints = None

        candidates = self.registry.generate_candidates(
            nodes,
            description,
            include_dynamic=bool(state.get("include_dynamic", True)),
            embedding_similarities=embedding_hints,
        )

        failed_locator = state.get("failed_locator")
        if failed_locator:
            failed_value = str(failed_locator.get("value") or "")
            adjusted: list[LocatorCandidate] = []
            for candidate in candidates:
                if failed_value and candidate.value == failed_value:
                    candidate = candidate.model_copy(
                        update={
                            "confidence": round(max(0.01, candidate.confidence * 0.25), 4),
                            "risks": [*candidate.risks, "Matches previously failed locator."],
                        }
                    )
                adjusted.append(candidate)
            candidates = self.registry.rank_candidates(adjusted)

        return {
            "candidate_nodes": nodes,
            "candidates": candidates,
            "trace": _append_trace(state, f"04_extract_and_generate:count={len(candidates)}"),
        }

    async def verify_and_rank(self, state: LocatorAgentState) -> dict[str, Any]:
        """Verify live candidates or preserve offline viability ranking."""
        candidates = list(state.get("candidates") or [])
        client = self.browser_client
        verified: list[LocatorCandidate] = []

        if client is not None and getattr(client, "page", None) is not None:
            verified = await client.verify_candidates(candidates, limit=8)
        else:
            for candidate in candidates:
                viable = candidate.confidence >= 0.45
                verified.append(
                    candidate.model_copy(
                        update={
                            "verified": viable,
                            "match_count": 1 if viable else 0,
                        }
                    )
                )

        ranked = self.registry.rank_candidates(verified)
        selected = ranked[0] if ranked else None
        return {
            "verified_candidates": ranked,
            "selected_candidate": selected,
            "trace": _append_trace(state, "05_verify_and_rank"),
        }

    def route_after_verification(
        self, state: LocatorAgentState
    ) -> Literal["heal_candidate", "finalize"]:
        """Route to healing while attempts remain, otherwise finalize."""
        selected = state.get("selected_candidate")
        attempts = int(state.get("healing_attempts") or 0)
        maximum = int(state.get("max_healing_attempts") or 2)
        failed_locator = state.get("failed_locator")
        needs_healing = (
            selected is None
            or (not selected.verified and attempts < maximum)
            or (failed_locator is not None and attempts < maximum and not state.get("healed"))
        )
        return "heal_candidate" if needs_healing else "finalize"

    async def heal_candidate(self, state: LocatorAgentState) -> dict[str, Any]:
        """Generate and rank fallback, chained, retry, and healing candidates."""
        attempts = int(state.get("healing_attempts") or 0) + 1
        nodes = list(state.get("candidate_nodes") or [])
        description = state.get("description") or ""
        existing = list(state.get("verified_candidates") or state.get("candidates") or [])
        healed_pool: list[LocatorCandidate] = []

        # Convert rich dynamic dictionaries through Pydantic and select healing strategies.
        for node in nodes:
            dynamic = self.registry.generate_dynamic_candidates(node, description)
            for item in dynamic:
                candidate = LocatorCandidate.model_validate(item)
                healed_pool.append(
                    candidate.model_copy(
                        update={
                            "verified": True,
                            "match_count": 1,
                            "confidence": round(min(0.95, max(candidate.confidence, 0.72)), 4),
                            "explanation": f"{candidate.explanation} (Healing attempt #{attempts})",
                        }
                    )
                )

        merged = self.registry.rank_candidates([*healed_pool, *existing])
        best = merged[0] if merged else None

        if self.vector_store is not None and best is not None:
            try:
                record = getattr(self.vector_store, "record_healed_locator", None)
                if callable(record):
                    record(
                        url=state.get("url") or "",
                        description=description,
                        candidate=best,
                    )
            except Exception:
                pass

        return {
            "healing_attempts": attempts,
            "verified_candidates": merged,
            "selected_candidate": best,
            "healed": best is not None,
            "trace": _append_trace(state, f"06_heal_candidate:attempt={attempts}"),
        }

    async def finalize_and_redact(self, state: LocatorAgentState) -> dict[str, Any]:
        """Build the redacted public response and optional report paths."""
        secrets = _collect_extra_secrets(state)
        warnings = [
            redact_text(item, extra_secrets=secrets) for item in (state.get("warnings") or [])
        ]
        auth = state.get("auth_outcome") or AuthenticationOutcome(
            status="skipped",
            sensitive_fields_redacted=True,
            message="Authentication not performed.",
        )
        ranked = list(state.get("verified_candidates") or state.get("candidates") or [])
        best = state.get("selected_candidate") or (ranked[0] if ranked else None)

        best_dict: dict[str, Any] | None = None
        evidence_dict: dict[str, Any] = {}
        matched = False
        if best is not None:
            matched = bool(best.verified or best.confidence >= 0.5)
            best_dict = redact_payload(
                {
                    "strategy": best.strategy.value,
                    "value": best.value,
                    "playwright_expr": best.playwright_expr,
                    "confidence": best.confidence,
                    "explanation": best.explanation,
                    "stability_score": best.stability_score,
                    "uniqueness_score": best.uniqueness_score,
                    "readability_score": best.readability_score,
                    "verified": best.verified,
                    "match_count": best.match_count,
                    "risks": best.risks,
                },
                extra_secrets=secrets,
            )
            evidence_dict = redact_payload(best.evidence, extra_secrets=secrets)

        alternatives: list[dict[str, Any]] = []
        for alternative in ranked[1:6]:
            alternatives.append(
                redact_payload(
                    {
                        "strategy": alternative.strategy.value,
                        "value": alternative.value,
                        "playwright_expr": alternative.playwright_expr,
                        "confidence": alternative.confidence,
                        "explanation": alternative.explanation,
                        "stability_score": alternative.stability_score,
                        "risks": alternative.risks,
                    },
                    extra_secrets=secrets,
                )
            )

        exported_files = dict(state.get("exported_files") or {})
        export_format = state.get("export_format")
        if self.exporter is not None and export_format and ranked:
            try:
                export_candidates = getattr(self.exporter, "export_candidates", None)
                if callable(export_candidates):
                    path = export_candidates(ranked, fmt=export_format)
                    exported_files[export_format] = redact_text(str(path), extra_secrets=secrets)
            except Exception as exc:
                warnings.append(
                    f"Export ({export_format}) skipped: {redact_text(str(exc), extra_secrets=secrets)}"
                )

        auth_dict = redact_payload(
            {
                "status": auth.status,
                "profile_name": auth.profile_name,
                "sensitive_fields_redacted": True,
                "message": auth.message,
            },
            extra_secrets=secrets,
        )
        trace = [
            redact_text(item, extra_secrets=secrets)
            for item in _append_trace(state, "07_finalize_and_redact")
        ]
        suggested_tests = [
            redact_text(item, extra_secrets=secrets)
            for item in _suggested_tests(best, state.get("description") or "")
        ]

        response = AgentResponse(
            success=True,
            matched=matched,
            best_locator=best_dict,
            alternatives=alternatives,
            authentication=auth_dict,
            warnings=warnings,
            evidence=evidence_dict,
            suggested_tests=suggested_tests,
            exported_files=exported_files,
            workflow_trace=trace,
        )
        return {
            "warnings": warnings,
            "suggested_tests": suggested_tests,
            "exported_files": exported_files,
            "trace": trace,
            "response": response,
        }


def build_locator_graph(runtime: LocatorGraphRuntime | None = None) -> Any:
    """Compile an optional LangGraph workflow, or return a local graph fallback."""
    rt = runtime or LocatorGraphRuntime()
    try:
        from langgraph.graph import END, StateGraph

        workflow: StateGraph[LocatorAgentState] = StateGraph(LocatorAgentState)
        workflow.add_node("validate_request", rt.validate_request)
        workflow.add_node("resolve_profile", rt.resolve_profile)
        workflow.add_node("capture_context", rt.capture_context)
        workflow.add_node("extract_and_generate", rt.extract_and_generate)
        workflow.add_node("verify_and_rank", rt.verify_and_rank)
        workflow.add_node("heal_candidate", rt.heal_candidate)
        workflow.add_node("finalize_and_redact", rt.finalize_and_redact)
        workflow.set_entry_point("validate_request")
        workflow.add_edge("validate_request", "resolve_profile")
        workflow.add_edge("resolve_profile", "capture_context")
        workflow.add_edge("capture_context", "extract_and_generate")
        workflow.add_edge("extract_and_generate", "verify_and_rank")
        workflow.add_conditional_edges(
            "verify_and_rank",
            rt.route_after_verification,
            {"heal_candidate": "heal_candidate", "finalize": "finalize_and_redact"},
        )
        workflow.add_edge("heal_candidate", "finalize_and_redact")
        workflow.add_edge("finalize_and_redact", END)
        return workflow.compile()
    except ImportError:
        from app.agent.graph import LocalLocatorGraph

        return LocalLocatorGraph(rt)


class LocalLocatorGraph:
    """Dependency-light fallback implementing the LangGraph node sequence."""

    def __init__(self, runtime: LocatorGraphRuntime) -> None:
        self.runtime = runtime

    async def ainvoke(self, state: LocatorAgentState) -> LocatorAgentState:
        """Execute all graph nodes locally and apply every returned state update."""
        current_dict: dict[str, Any] = dict(state).copy()

        async def apply(result: dict[str, Any]) -> None:
            current_dict.update(result)

        current = cast(LocatorAgentState, current_dict)
        await apply(await self.runtime.validate_request(current))
        current = cast(LocatorAgentState, current_dict)
        await apply(await self.runtime.resolve_profile(current))
        current = cast(LocatorAgentState, current_dict)
        await apply(await self.runtime.capture_context(current))
        current = cast(LocatorAgentState, current_dict)
        await apply(await self.runtime.extract_and_generate(current))
        current = cast(LocatorAgentState, current_dict)
        await apply(await self.runtime.verify_and_rank(current))
        current = cast(LocatorAgentState, current_dict)
        route = self.runtime.route_after_verification(current)
        if route == "heal_candidate":
            await apply(await self.runtime.heal_candidate(current))
            current = cast(LocatorAgentState, current_dict)
        await apply(await self.runtime.finalize_and_redact(current))
        return cast(LocatorAgentState, current_dict)
