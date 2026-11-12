#!/bin/sh
# Migrate the database, then serve the API. alembic upgrade head is idempotent,
# so this is safe to run on every start — the first run migrates an empty Neon
# database that Windows could not reach.
set -e

echo "mandate: applying migrations (alembic upgrade head)"
cd /app/packages/mandate-core
alembic upgrade head
cd /app

echo "mandate: starting API on 0.0.0.0:8001"
exec uvicorn mandate_api.app:app --app-dir services/api --host 0.0.0.0 --port 8001 ${RELOAD:+--reload}
