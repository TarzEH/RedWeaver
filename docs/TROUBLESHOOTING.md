# Troubleshooting

Common issues, what causes them, and how to fix them. Most problems are LLM-key,
rate-limit, or container-health related.

> Quick triage: `docker compose ps` (are all services healthy?) →
> `docker compose logs -f worker` (what is the run actually doing?).

---

## A run fails immediately

| Symptom (in the run / `error_message`) | Cause | Fix |
|----------------------------------------|-------|-----|
| `No LLM API key configured` | No key set for your user | Add a key in **Settings**, or set `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` in `.env`. |
| Provider `401 invalid_api_key` | The key is wrong/expired | Replace it. The stored error masks the key (`sk-proj-***REDACTED***`) by design — copy a fresh key from the provider dashboard. |
| Scope guard rejects the target | Target resolves to a private/metadata IP | RedWeaver refuses internal/`169.254.169.254`-style targets. Use a public host you're authorized to test. |

## A run hangs or never finishes

- **The watchdog** (`reap_stuck_runs`, Celery beat) auto-fails runs that exceed
  their `timeout_seconds` + grace, so a stranded run flips to **failed** on its own.
- If runs never start at all, the **worker** or **redis** is down:
  ```bash
  docker compose ps                 # worker up? redis healthy?
  docker compose logs --tail=100 worker
  docker compose restart worker beat
  ```

## A run "completes" but finds nothing useful

- **Rate limits** — large scans can hit your provider's tokens-per-minute cap.
  Look for `429 ... rate_limit_exceeded` in `docker compose logs worker`. Use a
  higher-tier key, a smaller model, or scope the hunt to fewer ATT&CK techniques.
- **CVE enrichment timed out** — `CVE lookup failed: read operation timed out`
  means a finding kept its uncorroborated CVSS/CVE. Re-run, or check outbound
  network access from the worker container.
- **Findings look hallucinated** — open `/debug/<runId>` and check the tool output
  behind the finding. No evidence → mark it a false positive in the Findings view.

## High token cost on a small target

A simple target costing millions of tokens usually means context is being re-sent
on every agent step. Pick a cheaper model for recon, scope the run to fewer
techniques, and watch the per-run cost badge.

## The frontend won't load / shows a blank page

```bash
docker compose logs --tail=50 frontend
docker compose up -d --build frontend   # rebuild after frontend changes
```

A `tsc` type error fails the frontend image build — check the build output for the
exact file and line.

## Login fails with the on-screen default credentials

The seeded admin is **`admin@redweaver.local` / `admin`** (from `DJANGO_SUPERUSER_*`).
If the login hint and the seeded user disagree, the seeded values win — or re-seed:

```bash
docker compose exec web python manage.py seed_admin
```

## Reset everything (local only — destroys data)

```bash
docker compose down -v     # -v also drops the Postgres volume
docker compose up -d --build
```

## Where to look

| Need | Where |
|------|-------|
| What a run did, step by step | `/debug/<runId>` (Behind the scenes) |
| Raw DB records | Django Admin at `http://localhost:8001/admin/` |
| Live worker activity | `docker compose logs -f worker` |
| API/web errors | `docker compose logs -f web` |
