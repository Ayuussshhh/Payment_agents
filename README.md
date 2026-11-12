# Mandate

An owner states a purchase rule. A published agent may prepare a cart. A deterministic policy decides. A payment provider is called only after that, and only for the cart that was approved.

The design is in [docs/ENGINE.md](docs/ENGINE.md). The running code is version 0.7 of the Mandate Core Engine.

| Specification | Subject |
| --- | --- |
| [docs/ENGINE.md](docs/ENGINE.md) | Cover and locked decisions |
| [docs/PRODUCT_VISION.md](docs/PRODUCT_VISION.md) | What the platform guarantees |
| [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md) | Processes, repository tree, both execution paths |
| [docs/ENGINE_DESIGN.md](docs/ENGINE_DESIGN.md) | Subsystems, contracts, LangGraph state |
| [docs/DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md) | PostgreSQL schema |
| [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) | Identity, CASL, financial checks |
| [docs/API_CONVENTIONS.md](docs/API_CONVENTIONS.md) | HTTP surface |
| [docs/DEVELOPMENT_STANDARDS.md](docs/DEVELOPMENT_STANDARDS.md) | Stack, rules, releases |
| [docs/IMPLEMENTATION_TICKETS.md](docs/IMPLEMENTATION_TICKETS.md) | First 30 days, then the later epics |

## Run it

The API listens on port 8001. The shell listens on port 3001.

```bash
uv sync --all-packages
uv run --directory services/api fastapi dev --port 8001
```

From `packages/mandate-core`:

```bash
uv run alembic upgrade head
```

From `apps/web`:

```bash
corepack pnpm install
corepack pnpm dev
```

Open http://localhost:3001. The page shows the engine name and version from `GET /v1`.

The engine runs on Python 3.10. Copy `.env.example` to `.env` and set `DATABASE_URL` before running migrations. Redis is optional: `/health` reports `redis: false` when it is down, and the process still answers.

## Tests

```bash
uv run pytest
```

Session, version, event, and organization tests run when `DATABASE_URL` points at PostgreSQL. The contract tests run without it.
