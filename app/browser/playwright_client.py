# SPDX-License-Identifier: MIT
"""Core Playwright browser automation client.

Core Stable: browser launch, navigation, login, DOM context, locator verification,
password-field masking, and bounded retries.
Optional: screenshot path retention and browser backend capabilities.
Experimental: visual-region and accessibility heuristics.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, cast

from playwright.async_api import Browser, BrowserContext, Locator, Page, async_playwright
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.api.schemas import AuthenticationResult as LegacyAuthenticationResult
from app.api.schemas import LoginProfile as LegacyLoginProfile
from app.browser.locator_registry import DOMNodeInfo, LocatorCandidate, LocatorStrategy
from app.browser.models import DOMSnapshot, ElementEvidence, VerificationEvidence
from app.security.redaction import redact_text

logger = logging.getLogger(__name__)


class BrowserLocatorLike(Protocol):
    """Subsurface of a Playwright locator used by mockable browser operations."""

    async def fill(self, value: str, **kwargs: object) -> None: ...

    async def click(self, **kwargs: object) -> None: ...

    async def count(self) -> int: ...

    async def is_visible(self) -> bool: ...

    async def wait_for(self, **kwargs: object) -> None: ...

    @property
    def first(self) -> BrowserLocatorLike: ...


class BrowserPageLike(Protocol):
    """Protocol representing a real or test-double Playwright page."""

    @property
    def url(self) -> str: ...

    def locator(self, selector: str) -> BrowserLocatorLike: ...

    def get_by_role(self, role: str, **kwargs: Any) -> BrowserLocatorLike: ...

    def get_by_label(self, text: str, **kwargs: Any) -> BrowserLocatorLike: ...

    def get_by_placeholder(self, text: str, **kwargs: Any) -> BrowserLocatorLike: ...

    def get_by_text(self, text: str, **kwargs: Any) -> BrowserLocatorLike: ...

    def get_by_test_id(self, test_id: str) -> BrowserLocatorLike: ...

    async def goto(
        self, url: str, *, wait_until: str = "domcontentloaded", timeout: int = 15000
    ) -> Any: ...

    async def title(self) -> str: ...

    async def evaluate(self, expression: str, arg: Any = None) -> Any: ...

    async def screenshot(self, **kwargs: Any) -> bytes: ...

    async def wait_for_timeout(self, timeout: int) -> None: ...


class LoginProfile(BaseModel):
    """Configurable authentication flow profile for a web application."""

    model_config = ConfigDict(extra="forbid")

    profile_name: str = Field(default="standard_form", min_length=1)
    username_selector: str = Field(
        default="input[name='username'], input[type='email'], #username", min_length=1
    )
    password_selector: str = Field(
        default="input[name='password'], input[type='password'], #password", min_length=1
    )
    submit_selector: str = Field(
        default="button[type='submit'], input[type='submit']", min_length=1
    )
    tenant_selector: str | None = None
    success_url_contains: str | None = None
    success_selector: str | None = None
    post_login_wait_ms: int = Field(default=500, ge=0, le=15_000)


class AuthenticationOutcome(BaseModel):
    """Sanitized authentication result without credential values."""

    model_config = ConfigDict(extra="forbid")

    status: str = "skipped"
    profile_name: str = "standard_form"
    sensitive_fields_redacted: bool = True
    message: str = ""


class SnapshotPayload(BaseModel):
    """Captured DOM, accessibility, text, and opt-in masked screenshot data."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(..., min_length=1)
    title: str = ""
    nodes: list[DOMNodeInfo] = Field(default_factory=list)
    accessibility_summary: list[dict[str, Any]] = Field(default_factory=list)
    visible_text: str = ""
    screenshot_b64: str | None = None
    password_fields_masked: bool = True


BUILTIN_LOGIN_PROFILES: dict[str, LoginProfile] = {
    "standard_form": LoginProfile(),
    "email_password_tenant": LoginProfile(
        profile_name="email_password_tenant",
        username_selector="input[type='email'], input[name='email']",
        password_selector="input[type='password'], input[name='password']",
        submit_selector="button[type='submit']",
        tenant_selector="input[name='tenant'], input[name='organization'], #tenant",
    ),
    "spa_token_form": LoginProfile(
        profile_name="spa_token_form",
        username_selector="input[autocomplete='username'], input[name='username']",
        password_selector="input[autocomplete='current-password'], input[type='password']",
        submit_selector="button:has-text('Sign in'), button:has-text('Log in'), button[type='submit']",
        post_login_wait_ms=1000,
    ),
}


def resolve_login_profile(profile: str | LoginProfile | None) -> LoginProfile:
    """Resolve a known profile name or custom profile without deriving credentials."""
    if isinstance(profile, LoginProfile):
        return profile
    if isinstance(profile, str) and profile.strip():
        key = profile.strip().lower()
        return BUILTIN_LOGIN_PROFILES.get(key, LoginProfile(profile_name=profile.strip()))
    return BUILTIN_LOGIN_PROFILES["standard_form"]


_EXTRACTION_SCRIPT = """
() => {
  const isVisible = (el) => {
    const style = window.getComputedStyle(el);
    if (!style || style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 || rect.height > 0;
  };
  const getLabelFor = (el) => {
    if (el.id) {
      const explicit = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (explicit && explicit.innerText) return explicit.innerText.trim();
    }
    const wrapped = el.closest('label');
    return wrapped && wrapped.innerText ? wrapped.innerText.trim() : null;
  };
  const getAncestry = (el) => {
    const chain = []; let curr = el.parentElement; let depth = 0;
    while (curr && depth < 5) {
      const tag = curr.tagName.toLowerCase();
      if (tag === 'html' || tag === 'body') break;
      chain.unshift(`${tag}${curr.id ? '#' + curr.id : ''}`);
      curr = curr.parentElement; depth += 1;
    }
    return chain;
  };
  const getNearbyText = (el) => {
    const parent = el.parentElement; if (!parent) return null;
    const raw = (parent.innerText || '').trim().replace(/\\s+/g, ' ');
    const own = (el.innerText || el.value || '').trim();
    const cleaned = own ? raw.replace(own, '').trim() : raw;
    return cleaned ? cleaned.slice(0, 120) : null;
  };
  const buildSimpleXPath = (el) => {
    if (el.id) return `//${el.tagName.toLowerCase()}[@id='${el.id}']`;
    const parts = []; let curr = el;
    while (curr && curr.nodeType === Node.ELEMENT_NODE && parts.length < 5) {
      const tag = curr.tagName.toLowerCase(); let idx = 1; let sib = curr.previousElementSibling;
      while (sib) { if (sib.tagName.toLowerCase() === tag) idx += 1; sib = sib.previousElementSibling; }
      parts.unshift(`${tag}[${idx}]`); curr = curr.parentElement;
    }
    return '//' + parts.join('/');
  };
  const buildSimpleCss = (el) => {
    const tag = el.tagName.toLowerCase();
    const testId = el.getAttribute('data-testid') || el.getAttribute('data-test-id');
    if (testId) return `${tag}[data-testid="${testId}"]`;
    if (el.id) return `#${el.id}`;
    const nameAttr = el.getAttribute('name'); if (nameAttr) return `${tag}[name="${nameAttr}"]`;
    const clsList = Array.from(el.classList || []).filter(c => c && c.length < 40).slice(0, 2);
    return clsList.length ? `${tag}.${clsList.join('.')}` : tag;
  };
  const targets = Array.from(document.querySelectorAll('a, button, input, select, textarea, [role], [data-testid], tr, td, th, label')).slice(0, 150);
  const nodes = targets.map el => {
    const rect = el.getBoundingClientRect(); const tag = el.tagName.toLowerCase();
    const ariaLabel = el.getAttribute('aria-label'); const labelText = getLabelFor(el);
    const rawText = tag === 'input' && el.type === 'password' ? '' : ((el.innerText || el.textContent || '').trim().slice(0, 200));
    const formEl = el.closest('form');
    return {
      tag, element_id: el.id || null, name: el.getAttribute('name') || null,
      classes: Array.from(el.classList || []).slice(0, 8), role: el.getAttribute('role') || null,
      accessible_name: ariaLabel || labelText || rawText || null, aria_label: ariaLabel || null,
      placeholder: el.getAttribute('placeholder') || null, text: rawText || null,
      test_id: el.getAttribute('data-testid') || el.getAttribute('data-test-id') || null,
      href: el.getAttribute('href') || null, input_type: el.getAttribute('type') || null,
      form_id: formEl ? (formEl.id || null) : null, label_text: labelText,
      nearby_text: getNearbyText(el), ancestry: getAncestry(el), xpath: buildSimpleXPath(el),
      css: buildSimpleCss(el), bbox: [Math.round(rect.x * 100) / 100, Math.round(rect.y * 100) / 100, Math.round(rect.width * 100) / 100, Math.round(rect.height * 100) / 100],
      visible: isVisible(el), attributes: {type: el.getAttribute('type') || undefined, disabled: el.hasAttribute('disabled') ? true : undefined}
    };
  });
  const accessibilitySummary = nodes.filter(n => n.role || n.accessible_name || ['a','button','input','select','textarea'].includes(n.tag)).slice(0,60).map(n => ({role:n.role || n.tag, name:n.accessible_name || '', tag:n.tag, visible:n.visible}));
  return {title: document.title || '', nodes, accessibility_summary: accessibilitySummary, visible_text: ((document.body && document.body.innerText) || '').trim().slice(0,4000)};
}
"""

_MASK_PASSWORDS_SCRIPT = """
() => {
  const inputs = Array.from(document.querySelectorAll('input[type="password"], input[name*="pass" i], input[id*="pass" i]'));
  for (const el of inputs) { el.value=''; el.setAttribute('value',''); el.style.filter='blur(8px)'; el.style.color='transparent'; el.style.textShadow='0 0 8px rgba(0,0,0,0.85)'; }
  return inputs.length;
}
"""


@dataclass
class PlaywrightClient:
    """Async browser client supporting real Playwright and injected test pages."""

    headless: bool = True
    timeout_ms: int = 15_000
    capture_screenshots: bool = False
    max_retries: int = 2
    page: BrowserPageLike | None = None
    screenshot_dir: Path | None = None
    _playwright_ctx: Any = field(default=None, init=False, repr=False)
    _browser: Any = field(default=None, init=False, repr=False)
    _context: Any = field(default=None, init=False, repr=False)
    _owns_browser: bool = field(default=False, init=False, repr=False)

    async def __aenter__(self) -> PlaywrightClient:
        await self.launch()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    def __post_init__(self) -> None:
        if self.screenshot_dir is not None:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def launch(self) -> None:
        """Launch Chromium unless an injected page is already present."""
        if self.page is not None:
            return
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("Install Playwright and Chromium before live browser use") from exc
        self._playwright_ctx = await async_playwright().start()
        self._browser = await self._playwright_ctx.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(ignore_https_errors=False)
        self._context.set_default_timeout(self.timeout_ms)
        self.page = await self._context.new_page()
        self._owns_browser = True

    async def close(self) -> None:
        """Close browser resources while suppressing teardown-only failures."""
        if not self._owns_browser:
            return
        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright_ctx is not None:
            try:
                await self._playwright_ctx.stop()
            except Exception:
                pass
        self._context = None
        self._browser = None
        self._playwright_ctx = None
        self.page = None
        self._owns_browser = False

    def _require_page(self) -> BrowserPageLike:
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")
        return self.page

    async def navigate(self, url: str) -> str:
        """Validate HTTP(S) and navigate to the caller-authorized target."""
        if not url.startswith(("http://", "https://")):
            raise ValueError("Target URL must use HTTP or HTTPS")
        page = self._require_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        return str(getattr(page, "url", url))

    async def authenticate(
        self,
        *,
        username: str | None = None,
        password: SecretStr | None = None,
        tenant: str | None = None,
        profile: str | LoginProfile | None = None,
    ) -> AuthenticationOutcome:
        """Execute a login profile without logging credentials."""
        resolved = resolve_login_profile(profile)
        secret = password.get_secret_value() if password is not None else None
        if not username and not secret and not tenant:
            return AuthenticationOutcome(status="skipped", profile_name=resolved.profile_name)
        page = self._require_page()
        try:
            if tenant and resolved.tenant_selector:
                await page.locator(resolved.tenant_selector).first.fill(
                    tenant, timeout=self.timeout_ms
                )
            if username:
                await page.locator(resolved.username_selector).first.fill(
                    username, timeout=self.timeout_ms
                )
            if secret:
                await page.locator(resolved.password_selector).first.fill(
                    secret, timeout=self.timeout_ms
                )
            if resolved.submit_selector:
                await page.locator(resolved.submit_selector).first.click(timeout=self.timeout_ms)
            if resolved.post_login_wait_ms:
                await page.wait_for_timeout(resolved.post_login_wait_ms)
            if resolved.success_selector:
                await page.locator(resolved.success_selector).first.wait_for(
                    state="visible", timeout=self.timeout_ms
                )
            current_url = str(getattr(page, "url", ""))
            if resolved.success_url_contains and resolved.success_url_contains not in current_url:
                return AuthenticationOutcome(
                    status="failed",
                    profile_name=resolved.profile_name,
                    message="Post-login URL did not match expected state",
                )
            return AuthenticationOutcome(status="success", profile_name=resolved.profile_name)
        except Exception as exc:
            safe = redact_text(str(exc), extra_secrets=[secret] if secret else None)
            return AuthenticationOutcome(
                status="failed",
                profile_name=resolved.profile_name,
                message=f"Authentication failed: {safe}",
            )
        finally:
            secret = None

    async def capture_snapshot(
        self, *, include_screenshot: bool | None = None, extra_secrets: list[str] | None = None
    ) -> SnapshotPayload:
        """Capture DOM nodes, accessibility summary, text, and optional masked screenshot."""
        page = self._require_page()
        should_capture = (
            self.capture_screenshots if include_screenshot is None else include_screenshot
        )
        raw = await page.evaluate(_EXTRACTION_SCRIPT)
        raw = raw if isinstance(raw, dict) else {}
        parsed: list[DOMNodeInfo] = []
        for item in raw.get("nodes") or []:
            if isinstance(item, dict) and item.get("tag"):
                try:
                    parsed.append(DOMNodeInfo.model_validate(item))
                except Exception:
                    continue
        screenshot_b64: str | None = None
        if should_capture:
            try:
                await page.evaluate(_MASK_PASSWORDS_SCRIPT)
                raw_bytes = await page.screenshot(full_page=False)
                if isinstance(raw_bytes, (bytes, bytearray)) and raw_bytes:
                    screenshot_b64 = base64.b64encode(bytes(raw_bytes)).decode("ascii")
            except Exception:
                screenshot_b64 = None
        return SnapshotPayload(
            url=redact_text(str(getattr(page, "url", "")), extra_secrets=extra_secrets)
            or "about:blank",
            title=redact_text(str(raw.get("title") or ""), extra_secrets=extra_secrets),
            nodes=parsed,
            accessibility_summary=list(raw.get("accessibility_summary") or []),
            visible_text=redact_text(
                str(raw.get("visible_text") or ""), extra_secrets=extra_secrets
            ),
            screenshot_b64=screenshot_b64,
            password_fields_masked=True,
        )

    def _resolve_playwright_locator(self, page: Any, candidate: LocatorCandidate) -> Any:
        """Translate a candidate to a real Playwright locator."""
        strategy = candidate.strategy
        val = candidate.value
        if strategy == LocatorStrategy.TEST_ID:
            cleaned = val.replace("[data-testid='", "").replace("']", "").strip('"')
            return page.get_by_test_id(cleaned)
        if strategy == LocatorStrategy.PLACEHOLDER:
            cleaned = val.replace("[placeholder='", "").replace("']", "").strip('"')
            return page.get_by_placeholder(cleaned)
        if strategy == LocatorStrategy.ACCESSIBLE_LABEL:
            cleaned = val.removeprefix("label=").strip('"').strip("'")
            return page.get_by_label(cleaned)
        if strategy == LocatorStrategy.TEXT:
            cleaned = val.removeprefix("text=").strip('"').strip("'")
            return page.get_by_text(cleaned, exact=False)
        if strategy in {LocatorStrategy.XPATH, LocatorStrategy.GENERATED_STABLE_XPATH}:
            xp = val if val.startswith("//") or val.startswith("(") else f"//{val}"
            return page.locator(f"xpath={xp}")
        return page.locator(val)

    async def verify_candidate(
        self, candidate: LocatorCandidate, *, retries: int | None = None
    ) -> LocatorCandidate:
        """Verify a candidate with bounded retries and update match evidence."""
        page = self._require_page()
        attempts = (self.max_retries if retries is None else retries) + 1
        last_count = 0
        for attempt in range(attempts):
            try:
                loc = self._resolve_playwright_locator(page, candidate)
                count = int(await loc.count())
                last_count = count
                if count >= 1:
                    visible = True
                    try:
                        visible = bool(await loc.first.is_visible())
                    except Exception:
                        visible = True
                    risks = list(candidate.risks)
                    if count > 1:
                        risks.append(f"Matched {count} elements; selector is not unique.")
                    if not visible:
                        risks.append("Matched element is currently hidden/not visible.")
                    conf_delta = 0.04 if count == 1 and visible else (-0.05 if count > 1 else -0.02)
                    return candidate.model_copy(
                        update={
                            "verified": True,
                            "match_count": count,
                            "confidence": round(
                                min(0.99, max(0.05, candidate.confidence + conf_delta)), 4
                            ),
                            "risks": risks,
                        }
                    )
            except Exception:
                pass
            if attempt < attempts - 1:
                await page.wait_for_timeout(150)
        return candidate.model_copy(
            update={
                "verified": False,
                "match_count": last_count,
                "confidence": round(max(0.05, candidate.confidence * 0.7), 4),
            }
        )

    async def verify_candidates(
        self, candidates: list[LocatorCandidate], *, limit: int = 8
    ) -> list[LocatorCandidate]:
        """Verify top candidates and leave later alternatives unverified."""
        verified: list[LocatorCandidate] = []
        for index, candidate in enumerate(candidates):
            verified.append(await self.verify_candidate(candidate) if index < limit else candidate)
        return verified


class _LegacyPlaywrightClient:
    """Owns an optional Playwright browser and performs safe page operations."""

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = 15_000,
        capture_screenshots: bool = False,
        screenshot_dir: Path | None = None,
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.capture_screenshots = capture_screenshots
        self.screenshot_dir = screenshot_dir or Path(".data/screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._playwright: Any = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> _LegacyPlaywrightClient:
        await self.launch()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    async def launch(self) -> None:
        """Launch an isolated Chromium browser context."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context()
        self._context.set_default_timeout(self.timeout_ms)

    async def close(self) -> None:
        """Close context and browser resources deterministically."""
        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        self._context = None
        self._browser = None
        self._playwright = None

    async def navigate(self, url: str) -> Page:
        """Navigate to a caller-authorized URL and return the active page."""
        if self._context is None:
            raise RuntimeError("Browser is not launched")
        if not url.startswith(("http://", "https://")):
            raise ValueError("Target URL must use HTTP or HTTPS")
        page = await self._context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        return page

    async def authenticate(
        self,
        page: Page,
        *,
        username: str,
        password: str,
        profile: LegacyLoginProfile,
        tenant: str | None = None,
    ) -> LegacyAuthenticationResult:
        """Authenticate through a configurable form profile without logging secrets."""
        if not username or not password:
            return LegacyAuthenticationResult(status="not_required", attempts=0)

        for attempt in range(1, 3):
            try:
                await page.fill(profile.username_selector, username)
                await page.fill(profile.password_selector, password)
                if tenant:
                    tenant_field = page.locator("[name='tenant'], [name='organization']")
                    if await tenant_field.count() > 0:
                        await tenant_field.first.fill(tenant)
                await page.click(profile.submit_selector)
                await page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)

                if profile.success_url_fragment:
                    if profile.success_url_fragment not in page.url:
                        continue
                if profile.success_text:
                    if await page.get_by_text(profile.success_text).count() == 0:
                        continue
                return LegacyAuthenticationResult(status="success", attempts=attempt)
            except Exception as exc:
                logger.warning("Authentication attempt failed: %s", type(exc).__name__)
                await asyncio.sleep(min(attempt * 0.25, 1.0))

        return LegacyAuthenticationResult(
            status="failed",
            attempts=2,
            message="Authentication did not reach the configured success state.",
        )

    async def capture_snapshot(
        self,
        page: Page,
        *,
        description: str,
    ) -> DOMSnapshot:
        """Capture text, DOM and an opt-in redacted screenshot."""
        del description
        html = await page.content()
        html = redact_text(html)
        visible_text = await page.locator("body").inner_text(timeout=self.timeout_ms)
        visible_text = redact_text(visible_text)

        accessibility: dict[str, object] = {}
        try:
            snapshot = await page.accessibility.snapshot()  # type: ignore[attr-defined]
            accessibility = snapshot if isinstance(snapshot, dict) else {}
        except (AttributeError, Exception):
            accessibility = {"available": False}

        screenshot_path: str | None = None
        if self.capture_screenshots:
            await page.evaluate(
                """
                () => {
                  for (const input of document.querySelectorAll('input[type="password"]')) {
                    input.style.filter = 'blur(8px)';
                    input.style.color = 'transparent';
                    input.value = '';
                  }
                }
                """
            )
            digest = hashlib.sha256(page.url.encode("utf-8")).hexdigest()[:12]
            candidate = self.screenshot_dir / f"page-{digest}.png"
            await page.screenshot(path=str(candidate), full_page=True)
            screenshot_path = str(candidate)

        return DOMSnapshot(
            url=page.url,
            title=redact_text(await page.title()),
            dom_html=html,
            visible_text=visible_text,
            accessibility_tree=accessibility,
            screenshot_path=screenshot_path,
        )

    async def verify_locator(
        self,
        page: Page,
        strategy: str,
        value: str,
    ) -> VerificationEvidence:
        """Resolve and verify a strategy against the live page."""
        loop = asyncio.get_running_loop()
        started = loop.time()
        locator: Locator
        try:
            if strategy == "role":
                match = value.lower()
                role = (
                    "button"
                    if "button" in match
                    else "textbox"
                    if "textbox" in match or "input" in match
                    else ""
                )
                name = value.split("name=", 1)[-1].strip("']") if "name=" in value else ""
                if role:
                    role_literal = cast(Any, role)
                    locator = page.get_by_role(role_literal, name=name or None)
            elif strategy == "text":
                locator = page.get_by_text(value, exact=False)
            elif strategy == "accessible_label":
                locator = page.get_by_label(value, exact=False)
            elif strategy == "test_id":
                locator = page.get_by_test_id(value)
            elif strategy in {"id", "name", "css", "xpath", "placeholder", "link_text"}:
                locator = page.locator(value)
            else:
                locator = page.locator(value)

            count = await locator.count()
            if count == 0:
                return VerificationEvidence(
                    verified=False,
                    match_count=0,
                    elapsed_ms=(loop.time() - started) * 1000,
                )

            first = locator.first
            visible = await first.is_visible()
            enabled = await first.is_enabled()
            return VerificationEvidence(
                verified=count == 1 and visible,
                match_count=count,
                unique_match=count == 1,
                visible=visible,
                enabled=enabled,
                elapsed_ms=(loop.time() - started) * 1000,
            )
        except Exception as exc:
            return VerificationEvidence(
                verified=False,
                match_count=0,
                elapsed_ms=(loop.time() - started) * 1000,
                error=redact_text(type(exc).__name__),
            )

    async def evidence_for_locator(self, page: Page, strategy: str, value: str) -> ElementEvidence:
        """Collect sanitized evidence for a verified locator."""
        verification = await self.verify_locator(page, strategy, value)
        if not verification.verified:
            return ElementEvidence()
        try:
            locator = page.locator(value)
            if await locator.count() == 0:
                return ElementEvidence()
            first = locator.first
            box = await first.bounding_box()
            tag = await first.evaluate("element => element.tagName.toLowerCase()")
            text = redact_text(await first.inner_text(timeout=self.timeout_ms))
            accessible_name = await first.evaluate(
                "element => element.getAttribute('aria-label') || element.innerText || ''"
            )
            return ElementEvidence(
                tag=str(tag),
                text=text,
                accessible_name=redact_text(str(accessible_name)),
                bbox=[float(box["x"]), float(box["y"]), float(box["width"]), float(box["height"])]
                if box
                else [],
            )
        except Exception:
            return ElementEvidence()
