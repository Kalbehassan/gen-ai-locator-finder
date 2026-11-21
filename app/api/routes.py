# SPDX-License-Identifier: MIT
"""FastAPI routes for the locator agent.

Core Stable: health, discovery and export endpoints.
All returned payloads pass through centralized redaction before serialization.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import (
    AgentResponse,
    AuthenticationResult,
    ExportRequest,
    LocatorRequest,
)
from app.config import Settings, get_settings
from app.reports.export import ReportExporter
from app.security.redaction import redact_payload

router = APIRouter()


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    """Return non-secret service health and provider mode."""
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "default_provider": settings.locator_default_provider,
        "vector_store": settings.locator_vector_store,
    }


@router.post("/locate", response_model=AgentResponse)
async def locate(
    request: LocatorRequest, settings: Settings = Depends(get_settings)
) -> AgentResponse:
    """Validate discovery request and return a redacted demonstration response.

    The browser-backed implementation is exercised by the local agent and CLI. API tests
    use an injected mock-compatible route response, while live browser calls remain explicit.
    """
    if not request.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="Target URL must use HTTP or HTTPS")

    return AgentResponse(
        success=False,
        matched=False,
        authentication=AuthenticationResult(status="skipped", sensitive_fields_redacted=True),
        warnings=[
            "Live discovery is not executed in the isolated API smoke route; use LocatorAgent or a configured browser client."
        ],
        alternatives=[],
    )


@router.post("/export")
async def export_report(
    request: ExportRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Export a response to local JSON, CSV and/or XLSX formats."""
    exporter = ReportExporter(settings.locator_reports_dir)
    safe_formats = list(dict.fromkeys(request.formats))
    outputs = exporter.export(request.response, safe_formats)  # type: ignore[arg-type]
    return dict(redact_payload({"success": True, "files": outputs}))
