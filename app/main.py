# SPDX-License-Identifier: MIT
"""FastAPI application entry point.

Core Stable: local API lifecycle and redaction logging filter.
Optional: OpenTelemetry is gated by settings and never imported by default.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings
from app.security.redaction import SecretRedactionFilter


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create local directories and configure process settings."""
    del application
    settings = get_settings()
    settings.ensure_local_directories()

    root_logger = logging.getLogger()
    root_logger.addFilter(SecretRedactionFilter())

    if settings.locator_enable_otel:
        try:
            from opentelemetry import trace  # type: ignore[import-not-found]
            from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]

            trace.set_tracer_provider(TracerProvider())
        except ImportError:
            logging.getLogger(__name__).warning(
                "OpenTelemetry requested but optional extra is not installed"
            )

    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Local-first authenticated UI locator discovery and self-healing API",
    lifespan=lifespan,
)
app.include_router(router)


def run() -> None:
    """Run the API from the console entry point."""
    current = get_settings()
    uvicorn.run(app, host=current.api_host, port=current.api_port)


if __name__ == "__main__":
    run()
