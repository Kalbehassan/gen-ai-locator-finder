# SPDX-License-Identifier: MIT
"""Application configuration for Gen-AI Locator Finder.

Supports local-first execution with default mock/local components while keeping
cloud LLM providers, heavy ML runtimes, distributed vector stores, and
OpenTelemetry optional and cleanly gated.

Core Stable: environment validation and local settings.
Optional Provider Integrations: LiteLLM and Gemini.
Experimental Demos: OpenTelemetry and provider switching.
Future Roadmap: centralized secret management.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local ``.env`` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="Gen-AI Locator Finder", min_length=1)
    app_env: Literal["local", "test", "staging", "production"] = Field(default="local")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    api_host: str = Field(default="127.0.0.1", min_length=1)
    api_port: int = Field(default=8000, ge=1, le=65535)

    locator_app_url: str | None = Field(default=None)
    locator_app_username: str | None = Field(default=None)
    locator_app_password: SecretStr | None = Field(default=None)
    locator_tenant: str | None = Field(default=None)
    locator_login_profile: str = Field(default="standard_form", min_length=1)

    locator_headless: bool = Field(default=True)
    locator_browser_timeout_ms: int = Field(default=15_000, ge=1_000, le=120_000)
    locator_capture_screenshots: bool = Field(default=False)
    locator_max_retries: int = Field(default=2, ge=0, le=10)

    locator_default_provider: Literal["mock", "litellm", "genai"] = Field(default="mock")
    locator_litellm_model: str = Field(default="gpt-4o-mini", min_length=1)
    locator_gemini_model: str = Field(default="gemini-2.5-flash", min_length=1)
    openai_api_key: SecretStr | None = Field(default=None)
    gemini_api_key: SecretStr | None = Field(default=None)
    locator_llm_timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)

    locator_vector_store: Literal["chroma", "milvus"] = Field(default="chroma")
    locator_chroma_dir: Path = Field(default=Path(".data/chroma"))
    locator_chroma_collection: str = Field(default="locator_candidates", min_length=1)
    locator_milvus_uri: str = Field(default="http://localhost:19530", min_length=1)
    locator_milvus_collection: str = Field(default="locator_candidates", min_length=1)

    locator_reports_dir: Path = Field(default=Path(".data/reports"))
    locator_enable_otel: bool = Field(default=False)
    locator_otel_service_name: str = Field(default="gen-ai-locator-finder", min_length=1)

    @field_validator("locator_app_url")
    @classmethod
    def validate_optional_url(cls, value: str | None) -> str | None:
        """Require environment target URLs to use HTTP or HTTPS."""
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("LOCATOR_APP_URL must start with http:// or https://")
        return cleaned

    @field_validator("locator_app_username", "locator_tenant")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        """Normalize whitespace-only optional text to ``None``."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None

    def resolve_target_credentials(
        self,
        username: str | None = None,
        password: SecretStr | None = None,
        tenant: str | None = None,
    ) -> tuple[str | None, SecretStr | None, str | None]:
        """Resolve credentials only from explicit arguments or environment settings."""
        resolved_username = (
            username.strip() if username and username.strip() else self.locator_app_username
        )
        resolved_password = password if password is not None else self.locator_app_password
        resolved_tenant = tenant.strip() if tenant and tenant.strip() else self.locator_tenant
        return resolved_username, resolved_password, resolved_tenant

    def ensure_local_directories(self) -> None:
        """Create local ChromaDB and report directories on first use."""
        self.locator_chroma_dir.mkdir(parents=True, exist_ok=True)
        self.locator_reports_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance for the current process."""
    return Settings()
