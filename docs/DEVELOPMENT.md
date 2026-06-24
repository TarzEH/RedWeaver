# Development

How to run RedWeaver for local development, iterate on the backend/frontend, and
run the checks CI runs.

---

## The Docker path (recommended)

Everything runs in containers — no local Python/Node/tool setup needed.

```bash
cp .env.example .env          # add your LLM key
docker compose up -d --build
```

| Service | Host port | Role |
|---------|-----------|------|
| `frontend` | 5173 | Vite-built UI (nginx) |
| `web` | 8001 → 8000 | Django ASGI (DRF + Channels/WebSocket) via daphne |
| `worker` / `beat` | — | Celery worker + scheduler |
| `postgres` | 5433 → 5432 | pgvector (system of record) |
| `redis` | 6380 → 6379 | Celery broker + channel layer |
| `knowledge` | 8100 | RAG knowledge service |

Common loops:

```bash
docker compose logs -f worker          # watch a run execute
docker compose exec web python manage.py shell    # Django shell against live DB
docker compose up -d --build frontend  # rebuild after frontend changes
docker compose up -d --build web worker # rebuild after backend changes
```

The `migrate` role (run on startup) applies migrations, collects static, seeds the
admin (`seed_admin`), and ingests the knowledge base (`ingest_kb`) — see
[`backend/entrypoint.sh`](../backend/entrypoint.sh).

## The non-Docker path (backend hacking)

You still need Postgres (with pgvector) and Redis reachable — easiest is to run
just those via Docker and the app on the host.

```bash
# infra only
docker compose up -d postgres redis knowledge

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL=postgres://...          # point at the docker postgres (port 5433)
export REDIS_URL=redis://localhost:6380/0
python manage.py migrate
python manage.py seed_admin

# ASGI server (WebSocket-capable) on :8000
daphne -b 0.0.0.0 -p 8000 redweaver.asgi:application

# in another shell: the Celery worker that actually runs hunts
celery -A redweaver worker -l info
```

Frontend dev server with hot reload (proxies `/api` and `/health` to `:8000`,
per [`vite.config.ts`](../frontend/vite.config.ts)):

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

## Checks (what CI enforces)

CI (`.github/workflows`) runs from `backend/`:

```bash
cd backend
pip install pytest ruff

# Lint (the exact paths CI checks)
ruff check apps/findings/risk.py apps/findings/attack_map.py \
  apps/hunts/costs.py apps/observability/confidence.py \
  redweaver_engine/tools/scope.py tests/

# Unit tests (pure functions, no DB)
pytest -q
```

Tests are deliberately **DB-free pure-function** tests (scope guard, risk scoring,
ATT&CK mapping, confidence, cost, redaction, noise ranking). Keep new unit-testable
logic in importable modules with no Django-model imports at module load, so it can
be tested without a configured Django.

Frontend build check (the same one the Docker image runs):

```bash
cd frontend && npm run build        # tsc -b && vite build
```

## Layout

| Path | What |
|------|------|
| `backend/apps/` | Django apps — `hunts` (runs), `findings`, `reports`, `observability`, `knowledge`, `agents`, `accounts`, `workspaces` |
| `backend/redweaver_engine/` | The CrewAI engine — `crews/`, `tools/`, `reports/`, `clients/`, `llm_factory.py` |
| `frontend/src/features/` | UI by feature — `dashboard`, `hunt`, `findings`, `report`, `debug`, `settings`, `knowledge` |
| `knowledge-base/` | The RAG corpus (markdown, 14 domains) |
| `docs/` | These guides |
