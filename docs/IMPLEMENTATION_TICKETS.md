# Implementation tickets

Status: specification v0.1, 11 November 2026.
Parent: [ENGINE.md](ENGINE.md).

The first 20 tickets are the next 30 days. They produce an engine that can execute a published agent through the model interface. They do not produce the studio.

The prototype in `gateway/` and `web/` keeps running. New code goes in `packages/mandate-core`, `services/api`, and `apps/web`. Nothing in these 20 tickets deletes the prototype.

A ticket is done when its tests pass and the exit line is true. A ticket that needs a product decision stops instead of guessing.

## Week 1 — foundation (v0.1)

### T01 — Package skeleton

Create the target tree from [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md): `packages/mandate-core`, `services/api`, `apps/web`. `mandate-core` is a uv package on Python 3.10. The API depends on it. The web app does not.

Done when `uv run python -c "import mandate_core"` works and the package contains empty modules for the eight subsystems plus `contracts`. No subsystem behavior.

### T02 — API and web processes boot

FastAPI serves `GET /health` and `GET /v1`. Next.js 16.4.6 serves a shell page that fetches `/v1` and shows the engine name and version. Port 8001 for the API so the prototype can stay on 8000.

Done when both processes start on Windows without Docker, and the shell renders the payload from `/v1`.

### T03 — PostgreSQL and the first migration

Alembic in `mandate-core` creates the schemas listed in [DATABASE_DESIGN.md](DATABASE_DESIGN.md). The first revision creates `identity.organizations`, `identity.memberships`, and `identity.role_bindings` only. Later tables land with the ticket that first writes them.

Done when `uv run alembic upgrade head` against PostgreSQL 18 succeeds on a second run without error.

### T04 — Redis connectivity

The API health payload includes `redis: true` when `PING` succeeds, and the process still serves `/health` with `redis: false` when Redis is down. No financial code path reads Redis.

Done when both health shapes are tested.

### T05 — Identity resolution test

Better Auth 1.7.20 is installed in `apps/web`. The migration that this ticket adds is the library's generated `auth` schema, committed through Alembic, plus the foreign link from `identity.memberships.user_id`. Mandate does not use Better Auth's organization plugin. The API resolves a session to a user and a membership, builds an `ExecutionContext`, and rejects a user with no membership.

Done when an automated test covers a valid session, a missing session, and a user who is not a member. CASL is not required for this ticket. The Python check is.

## Week 2 — contracts (v0.2)

### T06 — Contract models

Implement `ExecutionContext`, `EngineError`, `AgentDefinition`, `AgentVersion`, `Proposal`, `PolicyDecision`, and `EventEnvelope` from [ENGINE_DESIGN.md](ENGINE_DESIGN.md) as Pydantic models with `extra="forbid"`.

Done when a test shows that a model payload containing `permissions` or `organization_id` cannot construct an `ExecutionContext`, and that undeclared fields are rejected.

### T07 — Agent version repository

SQLAlchemy repositories for `agents.agents` and `agents.agent_versions`, including the immutability trigger. Publish inserts a new version. An update of `system_prompt` fails.

Done when a test publishes version 1 and version 2 and then fails an in-place edit.

### T08 — Outbox spine

`append_event` writes `events.outbox` and `events.audit_events` on the caller's transaction. A rolled-back transaction leaves neither row.

Done when a test commits one event and rolls back another.

### T09 — Organization scope

Repository reads require `organization_id` from the context. RLS policies for the tables that exist so far are enabled. The API role is not the owner.

Done when a test with the setting unset returns no rows, and a test with another organization id returns no rows.

### T10 — API error and correlation

The API maps `EngineError` to the error body in [API_CONVENTIONS.md](API_CONVENTIONS.md). Every response carries `X-Request-Id`.

Done when a forced `not_found` returns 404 with `code`, `message`, and `request_id`.

## Week 3 — model orchestration (v0.3)

### T11 — Provider interface and registry

`ModelProvider`, `ModelOrchestrator`, and `ModelCapabilities` exist. `StaticProvider` returns a canned tool call. The registry resolves a provider by name.

Done when a test looks up `static` and `openai` as different classes behind one interface. Until T12, the OpenAI class raises `model_unavailable` before any network call.

### T12 — OpenAI adapter

`invoke` and `stream` call the OpenAI API using the environment key. Errors are normalized to `EngineError`. The key is not copied onto the agent version or the response.

Done when a test double of the HTTP transport asserts the request shape, and a missing key returns `model_unavailable` without calling the network.

### T13 — Structured output

The orchestrator validates JSON responses with a Pydantic model the caller supplies. A status field on a policy draft is rejected by the draft model, not by the orchestrator special case.

Done when an extra field and a missing field each fail with `model_output_invalid`.

### T14 — Usage rows

Every successful invoke writes `usage.token_usage` with provider, model, run id when present, and token counts.

Done when the static provider records a row and a failed invoke does not pretend a call happened.

### T15 — Explicit fallback

A version may name a fallback. The orchestrator uses it only when the primary raises a provider error and the fallback's capabilities cover the request. A capability mismatch fails the call.

Done when one test switches to the fallback and one test refuses a fallback that lacks tool calling.

### T16 — Provider switch exit test

One runtime-free caller invokes "summarize this SKU" through the orchestrator twice, once with `static` and once with the OpenAI transport double. Business code between the two calls is the same function.

Done when that test is the v0.3 exit and it passes in CI without a live key.

## Week 4 — first runtime (v0.4)

### T17 — Buyer graph and factory

`graph_factory` builds a buyer graph from a published version. The graph uses `context_schema=GraphContext`. State is `BuyerState`. Tools offered to the model are the attached skills only.

Done when a graph built from a version that lists `propose` does not contain a PayPal tool, asserted by inspecting the tool list.

### T18 — Published-version resolution

`create_run` loads the requested version or the latest published version. It refuses an agent with no published version. The prompt executed is the prompt on that row.

Done when editing the agent name leaves the resolved prompt unchanged, and a run row points at `agent_version_id`.

### T19 — Checkpoint and resume

`AsyncPostgresSaver` is configured with `thread_id` equal to the run id. A test interrupts the graph after the fake skill, resumes, and observes the skill result still in state without a second skill execution.

Done when resume rebuilds `GraphContext` from the database rather than from the checkpoint. A revoked membership between the two calls fails resume.

### T20 — Trace, limits, and cancel

The run records model and skill trace events through the outbox. Limits stop the run at `limited`. `cancel_run` stops at the next super-step and leaves status `cancelled`.

Done when a two-step fake-model run completes with a trace, a tight `max_model_calls` ends `limited`, and cancel does not delete the proposal row the first step wrote. This is the 30-day exit.

## After day 30

These are epics. Break them into tickets at the start of the epic, using the same done-when style. Do not start an epic by building its screens.

| Epic | Release | Outcome |
| --- | --- | --- |
| E1 Skills | v0.5 | Register, version, attach, validate, and execute `list_products` and `propose`. Unattached skills fail. No uploaded code |
| E2 Policy | v0.6 | Port `decide` and the compiler draft rules. Pure evaluator. Porting-gate decision tests green |
| E3 Approval | v0.7 | Snapshot, expiry, revoke, signature stored, database row wins. A changed line invalidates the approval |
| E4 Commerce | v0.8 | State machine, PayPal sandbox adapter, idempotency, void on `intent_mismatch`, budget lock, webhooks, worker process. Live mode refused |
| E5 Audit completion | v0.9 | Timeline reconstructs the laptop workflow. Outbox worker marks published rows |
| E6 Studio | v0.9 | Dashboard, agents, models, skills, policies, approvals, playground, versions, runs, commerce, integrations, developers. Each page calls the API. Playwright covers the laptop path |
| E7 Developer platform | v0.9 | API keys, OpenAPI, webhook subscriptions, Python SDK, JavaScript SDK, sandbox versus a still-disabled live flag |
| E8 Hardening | v0.10 | The list below |

### v0.10 hardening list

- Multi-tenant tests beyond the RLS pair, including API keys.
- Payment recovery from `unknown` without a second create.
- Duplicate-request tests on every idempotent route.
- Model-provider outage uses the explicit fallback rules.
- Agent limit tests.
- Skill permission tests, including a skill that tries to call commerce.
- Policy property-based tests.
- Approval integrity tests, including a forged signature.
- Webhook replay protection.
- Backup and restore drill of PostgreSQL.
- Metrics and alerts on `unknown` transactions and failed runs.
- Load test of two concurrent reservations.
- API documentation published from OpenAPI.
- A new organization can sign up and run the laptop story in sandbox.

v1.0 is the release after that list, when the laptop workflow no longer needs a manual database edit.

## Tracker

Copy this into an issue list when implementation starts. Leave it unchecked in the specification.

Week 1: T01 T02 T03 T04 T05

Week 2: T06 T07 T08 T09 T10

Week 3: T11 T12 T13 T14 T15 T16

Week 4: T17 T18 T19 T20

0 / 20 complete.
