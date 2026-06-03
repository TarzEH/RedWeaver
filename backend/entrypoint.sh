#!/bin/sh
# RedWeaver backend entrypoint: wait for Postgres, then dispatch by role.
set -e

echo "[entrypoint] waiting for postgres..."
python - <<'PYEOF'
import os, sys, time
import psycopg
url = os.environ.get("DATABASE_URL", "")
for _ in range(60):
    try:
        psycopg.connect(url, connect_timeout=2).close()
        print("[entrypoint] postgres ready")
        sys.exit(0)
    except Exception as e:
        print("[entrypoint] waiting for db:", e)
        time.sleep(2)
print("[entrypoint] postgres unreachable")
sys.exit(1)
PYEOF

ROLE="${1:-web}"
echo "[entrypoint] role=$ROLE"
case "$ROLE" in
  migrate)
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    python manage.py seed_admin || true
    # Ingest the KB into pgvector (no-op if empty/no key; re-run after key set).
    python manage.py ingest_kb || true
    echo "[entrypoint] migrate role complete"
    ;;
  web)
    exec daphne -b 0.0.0.0 -p 8000 redweaver.asgi:application
    ;;
  worker)
    exec celery -A redweaver worker -l info --concurrency="${CREW_EXECUTOR_WORKERS:-4}"
    ;;
  beat)
    exec celery -A redweaver beat -l info
    ;;
  *)
    exec "$@"
    ;;
esac
