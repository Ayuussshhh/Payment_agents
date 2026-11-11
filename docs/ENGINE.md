# Mandate Core Engine — specification v0.1

Status: v0.1 is the running foundation. v0.2 adds the shared contracts. Dated 11 November 2026.
The earlier prototype in `gateway/` and `web/` has been removed. This specification remains the design for the engine.

Mandate is infrastructure for controlled agentic commerce. The product is the Mandate Core Engine. The web application, the SDKs, and any external purchasing agent are clients of that engine.

This file is the cover. The specification is split so each document has one job:

| Document | What it decides |
| --- | --- |
| [PRODUCT_VISION.md](PRODUCT_VISION.md) | Who the platform is for, and what it must guarantee |
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Processes, dependency direction, repository tree, the two execution paths |
| [ENGINE_DESIGN.md](ENGINE_DESIGN.md) | The eight subsystems, their interfaces, the domain contracts, and the LangGraph state |
| [DATABASE_DESIGN.md](DATABASE_DESIGN.md) | PostgreSQL schemas, keys, constraints, and the entity diagram |
| [SECURITY_MODEL.md](SECURITY_MODEL.md) | Authentication, the three permission planes, and the CASL catalog |
| [API_CONVENTIONS.md](API_CONVENTIONS.md) | HTTP conventions and the resource surface |
| [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md) | Stack baseline, engineering rules, releases, and the local environment |
| [IMPLEMENTATION_TICKETS.md](IMPLEMENTATION_TICKETS.md) | The first 30 days, then the later epics |

The design handbook in this folder (`index.html` and the pages it links) remains the research record: market, providers, and the original trust boundary. Where the handbook and this specification disagree about structure, this specification wins. The trust boundary does not move. An agent may prepare a purchase. A deterministic policy and a human approval decide. A payment provider is called only after that, and only for the cart that was approved.

## What changed in this revision

The previous build sequence started from screens and connected them afterward. This revision reverses that.

1. Build the Mandate Core Engine as an independently versioned Python package.
2. Expose it through FastAPI.
3. Build the Next.js Agent Studio as a client of that API, after the engine can already execute, decide, approve, and pay in tests.

The engine is a modular monolith. The eight subsystems below are modules with separate interfaces. They are not eight deployable services.

| Subsystem | Stable interface |
| --- | --- |
| Agent Runtime | `create_run`, `resume_run`, `cancel_run`, `get_run` |
| Model Orchestration | `invoke_model`, `stream_model`, `get_model_config` |
| Skill Runtime | `register_skill`, `validate_call`, `execute_skill` |
| Policy | `evaluate`, `explain`, `activate_policy` |
| Approval | `request_approval`, `approve`, `reject`, `expire` |
| Commerce | `prepare`, `authorize`, `capture`, `void`, `refund` |
| Event and Audit | `append_event`, `get_timeline`, `verify_history` |
| Identity | `authenticate`, `resolve_context`, `authorize_action` |

Those interfaces stay stable when an implementation behind them changes. Replacing LangGraph must not require a rewrite of the Policy Engine or the PayPal adapter.

## Decisions locked with this specification

These correct or tighten the draft plan. They are the baseline until a later specification changes them.

| Topic | Decision | Why |
| --- | --- | --- |
| Shape | One API process and, from the commerce release on, one worker process from the same package | Eight services would add network failures before there is a scale reason |
| Frontend | Next.js 16.4.6, App Router, JavaScript | Verified stable release, 9 November 2026. 16.5 is canary |
| Authorization UI | CASL `@casl/ability` 7.1.2 | Current line as of 10 November 2026. CASL 6.8.3 still receives fixes; a new application starts on 7 |
| Authentication | Better Auth 1.7.20 | Auth.js v5 has no stable release. `next-auth` latest is 4.24.15; v5 is `5.0.0-beta.32`, last published 20 July 2026. The identity port can take another provider later |
| What CASL is | Permission definitions for an authenticated user | CASL does not establish identity |
| Backend authorization | A Python authorizer on every protected operation | A browser CASL check never protects a payment |
| Agent orchestration | LangGraph 1.2.20, behind the runtime interface | Graph state is checkpointed. Trusted run context is passed as LangGraph runtime context and is rebuilt on resume |
| Policy | Deterministic Python. LangGraph may call it. The policy package does not import LangGraph | The same input and policy version always return the same decision |
| Payments | Commerce state machine plus provider adapters. PayPal sandbox is the first adapter | The agent runtime cannot move a payment from `authorized` to `captured` |
| Primary database | PostgreSQL 18.6 | 18.6 was released 13 August 2026. PostgreSQL 19 is still beta. Recheck for a newer 18.x patch at install |
| Cache | Redis 8.10.3 | 8.12 is a release candidate. Payment correctness does not depend on Redis |
| Object storage | None in the first releases | Configuration, events, and small artifacts live in PostgreSQL |
| Containers | None for development or for the first deployment description | Node, a Python virtual environment, local or managed PostgreSQL, and local or managed Redis |
| Prototype | `gateway/` and `web/` keep running | They are removed only after the engine passes the porting gate in [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md) |

The version table with the check date for every layer is in [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md). Lockfiles become the authority once implementation creates them.

## Two paths

An agent execution may reason, call permitted skills, and propose a purchase.

A financial execution rechecks policy, approval, and transaction state, and only then calls a payment provider.

The model has no edge that joins those paths. `propose` is a skill. `authorize` and `capture` are commerce operations.

## Three permission planes

They share an organization, and they are not interchangeable.

1. User permissions. What a person may do. CASL describes them. Python enforces them.
2. Agent permissions. Which skills and operations a published agent version may execute.
3. Financial permissions. Whether this cart, under this policy version, may be authorized or captured. The Policy Engine and the Approval Engine decide that.

A role that includes `approve` does not make a specific cart approvable. The policy result and the approval snapshot still have to match.

## Release order

Work follows dependency order. Weeks are planning targets for one person. A failed test moves the date. The phase text in the draft plan numbered the studio as both v0.9 and v0.10. This table is the one to follow.

| Release | Milestone | Target |
| --- | --- | --- |
| v0.1 | Technical foundation, including the event spine | Weeks 1–2 |
| v0.2 | Core engine contracts | Weeks 3–5 |
| v0.3 | Model orchestration | Weeks 6–7 |
| v0.4 | Agent runtime | Weeks 8–11 |
| v0.5 | Skills and tool engine | Weeks 12–14 |
| v0.6 | Policy engine | Weeks 15–17 |
| v0.7 | Approval engine | Weeks 18–19 |
| v0.8 | Commerce and PayPal | Weeks 20–23 |
| v0.9 | Event and audit completion, then Agent Studio and the developer platform | Weeks 24–27 |
| v0.10 | Security and reliability | Weeks 28–30 |
| v1.0 | Public beta | After the v0.10 gate, not on a calendar date |

Event rows are written from v0.1. v0.9 is when a full agent-to-payment workflow can be reconstructed from those records, and when the studio becomes a serious client. The studio does not become the place where policy or payment rules live.

The first 30 days are v0.1 through the start of v0.4. The goal of those 30 days is a published agent executing through the engine, with a real model call behind the model interface. It is not a polished dashboard.

## Exit of this specification

Implementation starts at ticket T01 in [IMPLEMENTATION_TICKETS.md](IMPLEMENTATION_TICKETS.md). T01 creates the package skeleton. It does not implement a subsystem.
