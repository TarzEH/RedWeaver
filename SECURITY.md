# Security

## Supported versions

Security fixes are applied on the latest `main` branch. Use tagged releases for production-like deployments when available.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for undisclosed security vulnerabilities.

- Email the maintainer(s) with a clear description, reproduction steps, and impact.
- Allow reasonable time for a fix before public disclosure.

## Deployment hygiene

- **Change the default demo password** after first login (see README). The seeded demo user exists only when the user store is empty.
- Set **`JWT_SECRET`** in `.env` (or your orchestrator) so authentication tokens remain valid across backend restarts and are not predictable.
- **Never commit** `.env`, API keys, or Redis dumps containing production data.
- **Scope** CORS with `CORS_ORIGINS` when exposing the API beyond localhost.
- Optional Redis Insight in `docker-compose.yml` is for **local debugging**; do not expose it publicly without authentication.

## Responsible use

Use RedWeaver only against systems you own or are authorized to test. See the README disclaimer.
