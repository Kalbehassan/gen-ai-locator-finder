# Credentials

The target URL, username, password, tenant and login profile are separate values. The application never guesses credentials from URL text or environment hostnames.

Use the API request:

```json
{
  "url": "https://authorized-example.invalid",
  "username": "fixture-user",
  "password": "fixture-password",
  "tenant": "fixture-tenant",
  "login_profile": "standard_form",
  "description": "Find the submit button"
}
```

The `password` field is Pydantic `SecretStr` and must not be copied into logs or reports.

Environment variables:

- `LOCATOR_APP_URL`
- `LOCATOR_APP_USERNAME`
- `LOCATOR_APP_PASSWORD`
- `LOCATOR_LOGIN_PROFILE`
- `LOCATOR_TENANT`

Store real values in a deployment secret manager or local `.env` excluded by Git. Keep fixtures synthetic. Interactive MFA, SSO, CAPTCHA and hardware-backed authentication require explicit operator authorization and are not automatically bypassed.
