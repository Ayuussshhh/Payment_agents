# Runs the Mandate Core Engine's HTTP edge on Linux.
#
# Windows Smart App Control blocks the unsigned native wheels this stack needs
# (psycopg, xxhash via LangGraph). They load normally on Linux, so the engine
# runs here while the Next.js UI stays native on Windows. The database is
# whatever DATABASE_URL points at — your Neon URL works unchanged.
FROM python:3.10-slim

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir "uv>=0.5"

WORKDIR /app

# The workspace is built from source, so copy it in, then resolve from the lock.
COPY . .
RUN uv sync --all-packages --frozen \
    && chmod +x docker-entrypoint.sh

EXPOSE 8001

ENTRYPOINT ["./docker-entrypoint.sh"]
