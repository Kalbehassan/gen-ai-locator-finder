# Security

## Credential separation

The target URL, username, password, tenant and login profile are separate values. The application never guesses credentials from URL text or hostnames.

## Central redaction

`app/security/redaction.py` recursively redacts Pydantic `SecretStr` values, sensitive key names, bearer/basic tokens, URL basic-auth credentials and configured secret strings before logging or export.

## Screenshots

Screenshots are disabled by default. Enabling them opts into local screenshot capture. Password inputs are visually blurred and their values cleared before the screenshot is taken. A caller must still avoid storing PII or session pages in unauthorized locations.

## Reports

JSON, CSV and XLSX reports are written only after central payload redaction. Reports are local runtime artifacts and are ignored by Git. The API never returns password values or provider API keys.

## Authorization

Automate only systems you are authorized to access. Do not bypass MFA, CAPTCHA, rate limits or account lockouts. Use synthetic fixtures for tests and a secret manager for real deployments.
