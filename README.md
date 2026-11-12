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

Requirements: Python 3.10, [uv](https://docs.astral.sh/uv/), Node.js with corepack, and PostgreSQL. Redis is optional.

1. Copy `.env.example` to `.env` and set `DATABASE_URL`. A `postgresql://` URL, including a hosted Neon URL, is rewritten to `postgresql+psycopg://`. Set `APPROVAL_SIGNING_KEY` and `BETTER_AUTH_SECRET` to random values.

2. Install and migrate:

   ```bash
   uv sync --all-packages
   cd packages/mandate-core && uv run alembic upgrade head
   ```

3. Start the API on port 8001:

   ```bash
   uv run --directory services/api fastapi dev --port 8001
   ```

4. Start the shell on port 3001, from `apps/web`:

   ```bash
   corepack pnpm install
   corepack pnpm dev
   ```

Open http://localhost:3001. The page shows the engine name and version from `GET /v1`. `GET /health` reports `database` and `redis` separately, and the process keeps answering when either is down.

## Tests

```bash
uv run python -m pytest
```

The contract, policy, and approval-logic tests run without a database. Tests that publish versions, write events, check organization isolation, or call the API need `DATABASE_URL` pointing at a migrated PostgreSQL database.

On Windows with Smart App Control turned on, Windows blocks the unsigned compiled modules in `psycopg[binary]` and `xxhash` (a LangGraph dependency). Only the tests that need neither will run. Run the full suite on a machine with Smart App Control off, or under WSL or in a container.

## Releases

See [CHANGELOG.md](CHANGELOG.md). v0.8, commerce and PayPal sandbox, is next.
