# SPDX-License-Identifier: MIT

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_locate_contract(client: TestClient) -> None:
    response = client.post(
        "/locate",
        json={
            "url": "https://example.invalid",
            "description": "Find the submit button",
            "login_profile": "standard_form",
            "password": "synthetic",
            "username": "fixture-user",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "success" in body
    assert "authentication" in body
    assert body["authentication"]["sensitive_fields_redacted"] is True
