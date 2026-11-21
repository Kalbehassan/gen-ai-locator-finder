# SPDX-License-Identifier: MIT

from pathlib import Path

from app.api.schemas import AgentResponse, AuthenticationResult
from app.reports.export import ReportExporter


def test_report_export(tmp_path: Path) -> None:
    response = AgentResponse(
        success=True,
        matched=True,
        authentication=AuthenticationResult(status="success"),
    )
    exporter = ReportExporter(tmp_path)
    outputs = exporter.export(response, ["json", "csv", "xlsx"])
    assert set(outputs) == {"json", "csv", "xlsx"}
    assert all(Path(path).exists() for path in outputs.values())
