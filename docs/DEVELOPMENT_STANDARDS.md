# Development standards

Status: specification v0.1, 11 November 2026.
Parent: [ENGINE.md](ENGINE.md).

## Stack baseline

Checked 11 November 2026. Exact versions are locked in `uv.lock` and `pnpm-lock.yaml` when those files are created. Until then, this table is the floor. Recheck patch releases at install. Do not adopt a release candidate to chase a higher number.

| Layer | Choice | Baseline |
| --- | --- | --- |
| Frontend | Next.js | 16.4.6, released 9 November 2026. The 16.5 line is canary |
| Frontend language | JavaScript | ES2024-compatible. The studio stays JavaScript, matching the current app |
| UI | MUI `@mui/material` | 9.5.0 |
| Styling | Tailwind CSS | 4.3.5. Next.js 16.4.6's installer pins Tailwind 4.3.3. Either 4.3.x is acceptable. Lock one |
| Authorization UI | CASL `@casl/ability` | 7.1.2, released 10 November 2026. CASL 6.8.3 is the previous line |
| Authentication | Better Auth | 1.7.20, released 10 November 2026. 1.8 is beta. Identity only, not the permission system |
| Backend language | Python | 3.10. The engine targets 3.10 |
| API | FastAPI | 0.162.4, released 10 November 2026 |
| Agent orchestration | LangGraph | 1.2.20, released 5 November 2026, plus `langgraph-checkpoint-postgres` |
| Validation | Pydantic | 2.14.3. Major 2 only |
| ORM | SQLAlchemy | 2.0.x, at least 2.0.36. The 2.1 line publishes wheels from Python 3.13 upward |
| Migrations | Alembic | 1.20.1, released 21 October 2026. The 1.20.2 notes on the documentation site have no release date. Do not pin an unreleased Alembic |
| Database | PostgreSQL | 18.6, released 13 August 2026. PostgreSQL 19 is beta. Recheck for a newer 18.x patch before installing |
| Vector | pgvector | A release that supports PostgreSQL 18, locked at install. Unused in the first 30 days |
| Cache | Redis | 8.10.3, released 26 October 2026. 8.12 is a release candidate |
| Python environment | uv | Current stable, committed as `uv.lock` |
| JavaScript packages | pnpm | Current stable, committed as `pnpm-lock.yaml` |
| Python tests | pytest | Current stable |
| Browser tests | Playwright | Current stable, from the first studio flow that a person can click |
| Tracing | LangSmith | Off unless `LANGSMITH_TRACING` is set |
| Telemetry | OpenTelemetry | Stable API SDK, wired on the API process when the first commerce release needs it |
| API description | OpenAPI | 3.1 |

Auth.js is not the baseline. The reason is in [SECURITY_MODEL.md](SECURITY_MODEL.md). CASL 6.x is not the baseline either. Both corrections are version facts from this check, not a change to the permission design. CASL still defines abilities. Python still enforces them. Something other than CASL still has to establish identity, and that something is Better Auth.

MUI and Tailwind both stay, as requested. MUI is for application components. Tailwind is for layout. One set of color and spacing tokens is defined in the web app and consumed by both. v0.1 does not build a separate design system.

## Environment

No Docker. No Docker Compose. No S3.

PostgreSQL and Redis run as local installations or managed services. The API, the worker, and Next.js are ordinary processes.

```bash
# from services/api
uv run fastapi dev

# from packages/mandate-core
uv run alembic upgrade head

# from apps/web
pnpm dev
```

On Windows the same commands run in PowerShell. The prototype's `python -m venv` flow stays documented in the root README until the prototype is retired.

Environment variables for the new processes:

```
DATABASE_URL=postgresql+psycopg://mandate:mandate@localhost:5432/mandate
REDIS_URL=redis://localhost:6379/0
BETTER_AUTH_SECRET=
OPENAI_API_KEY=
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_ENV=sandbox
```

`PAYPAL_ENV=live` is rejected by the v0.8 adapter. Changing that is a later decision, not a flag someone flips in development.

## Testing

| Test | Where it lives | Rule |
| --- | --- | --- |
| Policy, hash, money, approval binding | `packages/mandate-core/tests` | No network, no FastAPI, no real PayPal |
| Provider adapter | Same package, against a fake transport and, optionally, sandbox | The fake is the CI default |
| HTTP mapping | `services/api/tests` | Uses the engine with fakes |
| Authorization | Both | Every new route has a forbidden-role test and a cross-organization test |
| Browser | `apps/web` Playwright | A flow is clicked through, not only screenshotted, once the studio owns that flow |

The porting gate is the prototype suite, re-expressed against the engine. v0.8 is not done until these pass:

- The demo sentence compiles hard fields and leaves "good battery life" as a preference.
- "Around $800" and "a good laptop" do not activate.
- The compiler cannot set status active.
- A valid Dell needs approval, then allows when the approval matches.
- Over budget, brand, addon, RAM, and storage return the existing reason codes.
- A suggested price is ignored.
- The canonical hash is stable across key order.
- A changed price voids and does not capture.
- Order creation is idempotent.
- Two reservations cannot both spend the last minor units.

Property-based tests for the policy evaluator are part of v0.10, after the examples are green. They are not a substitute for those examples.

## Engineering rules

The table in [SECURITY_MODEL.md](SECURITY_MODEL.md) is binding. Two process rules sit beside it:

1. A subsystem's public behavior changes by changing its tests in the same revision as its code.
2. A permission string changes by editing `contracts/permissions.json` and the tests that load it on both sides. Handwritten one-off ability checks are a defect.

## Logging

Structured logs, one JSON object per line, with `request_id`, `organization_id`, and `code` when there is an error. Prompt text and catalog descriptions are not logged at info. Provider responses are stored redacted in `payment_attempts`, not printed in full.

## Release gate

A release version is cut when its exit condition in [ENGINE.md](ENGINE.md) is true and its tests are green. The week numbers are capacity planning for one person. They do not override a red test.

| Release | Exit condition |
| --- | --- |
| v0.1 | Web shell and API start, Alembic upgrades a PostgreSQL 18 database, Redis answers, an authentication test resolves a user and an organization |
| v0.2 | Engine subsystems exchange the contract models with no web types involved |
| v0.3 | One caller switches provider by configuration |
| v0.4 | A published agent runs, calls a fake skill, checkpoints, resumes, and emits a trace |
| v0.5 | Skills can be registered, versioned, attached, rejected when unattached, and executed |
| v0.6 | The same proposal and policy version always produce the same decision |
| v0.7 | One exact approval dies when the cart changes |
| v0.8 | A sandbox or fake-provider purchase is created, authorized, revalidated, captured or voided, with one transaction row |
| v0.9 | That workflow can be rebuilt from the audit timeline, and the studio is a client rather than the owner of the rules |
| v0.10 | The hardening list in [IMPLEMENTATION_TICKETS.md](IMPLEMENTATION_TICKETS.md) is done |
| v1.0 | The laptop workflow runs without anyone editing the database by hand |

## What v0.1 explicitly leaves out

Microservices, Docker, S3, Neo4j, user-uploaded skill code, live PayPal, voice authentication, multi-step approval chains, policy simulation UI, and a polished studio. Several of those are real later releases. They are not part of the foundation.
