# Mandate

An owner states a purchase rule. A published agent may prepare a cart. A deterministic policy decides. A payment provider is called only after that, and only for the cart that was approved.

The design is in [docs/ENGINE.md](docs/ENGINE.md). The running code is version 0.8 of the Mandate Core Engine.

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

Requirements: [uv](https://docs.astral.sh/uv/), Node.js with corepack, PostgreSQL (a hosted Neon URL is fine), and — on Windows — Docker Desktop (see below). Python 3.10 is used inside the container or venv. Redis is optional.

Copy `.env.example` to `.env` first. Set `DATABASE_URL` (a `postgresql://` URL, including Neon, is rewritten to `postgresql+psycopg://`), and set `APPROVAL_SIGNING_KEY` and `BETTER_AUTH_SECRET` to random values. For the model, set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `MODEL`.

### On Windows (Smart App Control) — run the engine in Docker

Windows Smart App Control blocks the unsigned native wheels this stack needs (`psycopg`, and `xxhash` via LangGraph), so the Python process cannot start natively. Run it on Linux in a container instead — it uses the same `DATABASE_URL` from your `.env`, so your Neon database is unchanged. The UI stays native on Windows.

```bash
docker compose up --build        # migrates the database, then serves the API on :8001
```

Then start the UI natively, from `apps/web`:

```bash
corepack pnpm install
corepack pnpm dev                # http://localhost:3001
```

The UI and the API must share one database. Keep the web app's database pointed at the same `DATABASE_URL` (your Neon URL) that the API container uses.

### On Linux / macOS / WSL — run it natively

```bash
uv sync --all-packages
cd packages/mandate-core && uv run alembic upgrade head
uv run --directory ../../services/api fastapi dev --port 8001
```

Then the UI, from `apps/web`: `corepack pnpm install && corepack pnpm dev`.

Open http://localhost:3001. The page shows the engine name and version from `GET /v1`. `GET /health` reports `database` and `redis` separately, and the process keeps answering when either is down.

### First run

1. Go to **/sign-in** and create a workspace. Sign-up also calls `POST /v1/onboarding`, which gives you an organization and an owner role.
2. **Policies** — compile a plain-language rule, then activate the draft (ambiguous rules can't be activated).
3. **Approvals** — evaluate a catalog SKU against the active policy, open an approval, and approve it.
4. **Payments** — create a payment from the valid approval, then authorize and capture. A changed cart voids with `intent_mismatch` instead of capturing. Needs `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` in `.env`.
5. **Agents** — create an agent, publish a version, and run it. Runs need a model key (`OPENAI_API_KEY`).

## Tests

```bash
uv run python -m pytest
```

The contract, policy, and approval-logic tests run without a database. Tests that publish versions, write events, check organization isolation, or call the API need `DATABASE_URL` pointing at a migrated PostgreSQL database.

On Windows with Smart App Control turned on, Windows blocks the unsigned compiled modules in `psycopg[binary]` and `xxhash` (a LangGraph dependency). Only the tests that need neither will run. Run the full suite in the container (`docker compose run --rm api uv run python -m pytest`), under WSL, or on a machine with Smart App Control off.

## Releases

See [CHANGELOG.md](CHANGELOG.md). v0.8, commerce and PayPal sandbox, is next.
