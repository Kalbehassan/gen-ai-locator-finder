# SPDX-License-Identifier: MIT
"""Shared pytest fixtures containing synthetic data only."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Create an isolated FastAPI TestClient."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def synthetic_password() -> str:
    """Synthetic password value used only for redaction tests."""
    return "synthetic-not-a-real-secret"
