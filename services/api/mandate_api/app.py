"""Mandate platform API. This process calls the engine. It does not own policy or payment rules."""

import os
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from mandate_core import __version__
from mandate_core.settings import database_url as configured_database_url
from mandate_core.settings import model_configured, model_name, model_provider
from mandate_core.contracts.models import ModelRef
from mandate_core.errors import EngineError
from mandate_core.identity import resolve_execution_context
from mandate_core.identity import api_keys as api_keys_store
from mandate_core.identity.onboarding import bootstrap_membership
from mandate_core.identity.catalog import expand_roles
from mandate_core.contracts import ExecutionContext
from mandate_core.audit import get_timeline, verify_history
from mandate_core.models import read_usage
from mandate_core.approval import ApprovalEngine
from mandate_core.policy import ModelDrafter, PolicyEngine
from mandate_core.models import ModelOrchestrator, SqlUsage, default_registry
from mandate_core.agent import agent_shop
from mandate_core.commerce import CommerceEngine, PayPalProvider, handle_webhook
from mandate_core.skills import SkillRuntime
from mandate_core.skills.catalog import list_products
from mandate_core.persistence.agents import AgentRepository
from mandate_core.runtime import AgentRuntime, OrchestratedModel
from mandate_core.runtime.sql_store import SqlRuntimeStore
from langgraph.checkpoint.memory import InMemorySaver

RESOURCES = [
    {"method": "GET", "path": "/health", "purpose": "Process, database, and Redis connectivity."},
    {"method": "GET", "path": "/v1", "purpose": "Engine name, package version, and this resource list."},
    {"method": "GET", "path": "/v1/context", "purpose": "Resolve a session into an execution context."},
    {"method": "POST", "path": "/v1/onboarding", "purpose": "Give a new signed-in user an organization and owner role."},
    {"method": "POST", "path": "/v1/agents", "purpose": "Create an agent definition."},
    {"method": "GET", "path": "/v1/agents/{id}", "purpose": "Read one agent in the caller's organization."},
    {"method": "POST", "path": "/v1/agents/{id}/versions", "purpose": "Publish an immutable agent version."},
    {"method": "POST", "path": "/v1/agents/{id}/runs", "purpose": "Run a published agent version."},
    {"method": "POST", "path": "/v1/runs/{id}/resume", "purpose": "Resume a paused run."},
    {"method": "POST", "path": "/v1/runs/{id}/cancel", "purpose": "Stop a run at the next step. Does not void a payment."},
    {"method": "GET", "path": "/v1/runs/{id}", "purpose": "Read a run, its trace, and its proposal ids."},
    {"method": "GET", "path": "/v1/models", "purpose": "Provider names and capability metadata. No secrets."},
    {"method": "GET", "path": "/v1/skills", "purpose": "Skills that can be attached. PayPal is not a skill."},
    {"method": "POST", "path": "/v1/policies", "purpose": "Compile an instruction into a draft policy version."},
    {"method": "GET", "path": "/v1/policies", "purpose": "List policy versions. Active versions are not edited in place."},
    {"method": "POST", "path": "/v1/policies/{id}/activate", "purpose": "Activate a draft that has no ambiguities."},
    {"method": "POST", "path": "/v1/decisions", "purpose": "Evaluate one catalog SKU. The catalog owns the price."},
    {"method": "POST", "path": "/v1/proposals", "purpose": "Evaluate one catalog SKU. Same decision as /v1/decisions."},
    {"method": "POST", "path": "/v1/approvals", "purpose": "Open an approval for one evaluated cart."},
    {"method": "GET", "path": "/v1/approvals", "purpose": "List approvals in the caller's organization."},
    {"method": "GET", "path": "/v1/approvals/{id}", "purpose": "Read one approval snapshot, hash, expiry, and status."},
    {"method": "POST", "path": "/v1/approvals/{id}/approve", "purpose": "Bind the caller to that exact cart."},
    {"method": "POST", "path": "/v1/approvals/{id}/reject", "purpose": "Reject a pending approval or revoke a valid one."},
    {"method": "GET", "path": "/v1/catalog", "purpose": "The merchant catalog the skill reads. Prices are minor units."},
    {"method": "POST", "path": "/v1/agent/shop", "purpose": "An AI agent picks a SKU for a goal; the policy decides."},
    {"method": "POST", "path": "/v1/payments", "purpose": "Reserve budget and create a provider order for the approved amount."},
    {"method": "POST", "path": "/v1/payments/{id}/authorize", "purpose": "Authorize the provider order this payment created."},
    {"method": "POST", "path": "/v1/payments/{id}/capture", "purpose": "Capture when the catalog hash still matches. Otherwise void."},
    {"method": "POST", "path": "/v1/payments/{id}/void", "purpose": "Void an open authorization."},
    {"method": "POST", "path": "/v1/payments/{id}/refund", "purpose": "Refund a capture, full amount in this release."},
    {"method": "GET", "path": "/v1/payments/{id}", "purpose": "Transaction, attempts, and reason code."},
    {"method": "POST", "path": "/v1/providers/paypal/webhook", "purpose": "Verified provider events only."},
    {"method": "GET", "path": "/v1/timeline", "purpose": "Audit timeline for an aggregate, type and id query."},
    {"method": "GET", "path": "/v1/usage", "purpose": "Token counts for the organization."},
    {"method": "POST", "path": "/v1/api-keys", "purpose": "Create a key. The secret is in this response only."},
    {"method": "GET", "path": "/v1/api-keys", "purpose": "List keys. Secrets are never returned again."},
    {"method": "POST", "path": "/v1/api-keys/{id}/revoke", "purpose": "Revoke a key immediately."},
]


class AgentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str = ""
    graph_kind: Literal["compiler", "buyer"] = "buyer"


class VersionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str
    provider: str
    model: str
    temperature: float = 0


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: dict = Field(default_factory=dict)


class ShopIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_id: UUID
    goal: str = ""


class PolicyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instruction: str = Field(min_length=1)


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_id: UUID
    sku: str = Field(min_length=1)
    suggested_unit_amount_minor: int | None = None


class ApprovalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: UUID


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = ""


class PaymentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: UUID
    approval_id: UUID


class AuthorizeTxnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: str = Field(min_length=1)


class RefundTxnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount_minor: int | None = None


class ApiKeyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)


class OnboardingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_name: str = ""


def database_ok(engine: Engine | None) -> bool:
    if engine is None:
        return False
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        return True
    except Exception:
        return False


def redis_ok(client) -> bool:
    if client is None:
        return False
    try:
        return bool(client.ping())
    except Exception:
        return False


def create_app(database_url: str | None = None, redis_client=None, engine: Engine | None = None) -> FastAPI:
    app = FastAPI(title="Mandate", version="v1")
    database_url = database_url if database_url is not None else configured_database_url()
    if engine is None and database_url:
        engine = create_engine(database_url, pool_pre_ping=True)
    if redis_client is None and os.environ.get("REDIS_URL"):
        redis_client = Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=0.3)
    app.state.engine = engine
    app.state.redis = redis_client
    app.state.checkpointer = InMemorySaver()
    app.state.registry = default_registry()
    app.state.model_ref = ModelRef(provider=model_provider(), model=model_name())
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ],
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        incoming = request.headers.get("x-request-id") or f"req_{uuid4().hex}"
        request.state.request_id = incoming
        response = await call_next(request)
        response.headers["X-Request-Id"] = incoming
        return response

    @app.exception_handler(EngineError)
    def engine_error(request: Request, exc: EngineError):
        request_id_value = getattr(request.state, "request_id", "")
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": request_id_value,
                    "details": exc.details,
                }
            },
            headers={"X-Request-Id": request_id_value},
        )

    @app.get("/v1/skills")
    def skills():
        return {"skills": SkillRuntime().list_skills()}

    @app.get("/v1/models")
    def models():
        return {"providers": default_registry().catalog()}

    @app.get("/health")
    def health():
        return {"ok": True, "database": database_ok(app.state.engine), "redis": redis_ok(app.state.redis)}

    @app.get("/v1")
    def contract():
        return {"name": "Mandate", "version": "v1", "engine_version": __version__, "resources": RESOURCES}

    agents = AgentRepository()
    policies = PolicyEngine()
    approvals = ApprovalEngine()

    def bearer(request: Request) -> str:
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            return ""
        return header.removeprefix("Bearer ").strip()

    def require_engine():
        if app.state.engine is None:
            raise EngineError("database_unavailable", "The database is not configured.", 503)

    def require_session(request: Request) -> str:
        token = bearer(request)
        if not token:
            raise EngineError("unauthenticated", "A session token is required.", 401)
        require_engine()
        return token

    @app.post("/v1/onboarding")
    def onboarding(body: OnboardingIn, request: Request):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            result = bootstrap_membership(connection, token, body.organization_name, request.state.request_id)
        return {"onboarding": result}

    @app.get("/v1/context")
    def context(request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=organization_id,
                request_id=request.state.request_id,
            )
        return {"context": resolved.model_dump(mode="json")}

    @app.post("/v1/agents")
    def create_agent(body: AgentIn, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=organization_id,
                request_id=request.state.request_id,
            )
            created = agents.create_agent(connection, resolved, body.name, body.description, body.graph_kind)
        return {"agent": created.model_dump(mode="json")}

    @app.get("/v1/agents/{agent_id}")
    def read_agent(agent_id: UUID, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=organization_id,
                request_id=request.state.request_id,
            )
            found = agents.get_agent(connection, resolved, agent_id)
        return {"agent": found.model_dump(mode="json")}

    @app.post("/v1/agents/{agent_id}/versions")
    def publish_agent(agent_id: UUID, body: VersionIn, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=organization_id,
                request_id=request.state.request_id,
            )
            published = agents.publish_version(
                connection,
                resolved,
                agent_id,
                provider=body.provider,
                model=body.model,
                temperature=body.temperature,
                system_prompt=body.prompt,
            )
        return {"version": published.model_dump(mode="json")}

    def runtime_for(connection):
        def model_factory(context, run, version):
            return OrchestratedModel(app.state.registry, context, version, run.id, SqlUsage(connection))

        return AgentRuntime(SqlRuntimeStore(connection), app.state.checkpointer, model_factory=model_factory)

    @app.post("/v1/agents/{agent_id}/runs")
    async def start_run(agent_id: UUID, request: Request, body: RunIn | None = None):
        token = require_session(request)
        run_input = body.input if body is not None else {}
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=None,
                request_id=request.state.request_id,
            )
            run = await runtime_for(connection).create_run(resolved, agent_id, None, run_input)
        return {"run": run.model_dump(mode="json")}

    @app.post("/v1/runs/{run_id}/resume")
    async def resume_run(run_id: UUID, request: Request):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=None,
                request_id=request.state.request_id,
            )
            run = await runtime_for(connection).resume_run(resolved, run_id, None)
        return {"run": run.model_dump(mode="json")}

    @app.post("/v1/runs/{run_id}/cancel")
    async def cancel_run(run_id: UUID, request: Request):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=None,
                request_id=request.state.request_id,
            )
            run = await runtime_for(connection).cancel_run(resolved, run_id)
        return {"run": run.model_dump(mode="json")}

    @app.get("/v1/runs/{run_id}")
    def read_run(run_id: UUID, request: Request):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=None,
                request_id=request.state.request_id,
            )
            run = runtime_for(connection).store.get_run(resolved.organization_id, run_id)
        if run is None:
            raise EngineError("not_found", "That run does not exist.", 404)
        return {"run": run.model_dump(mode="json")}

    def require_idempotency(request: Request) -> str:
        key = (request.headers.get("idempotency-key") or "").strip()
        if not key:
            raise EngineError("idempotency_key_required", "An Idempotency-Key header is required.", 400)
        return key

    def policy_drafter():
        if not model_configured():
            return None
        return ModelDrafter(app.state.registry, app.state.model_ref)

    @app.post("/v1/agent/shop")
    async def agent_shop_route(body: ShopIn, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(connection, token, organization_id=organization_id, request_id=request.state.request_id)
            orchestrator = ModelOrchestrator(app.state.registry, SqlUsage(connection))
            result = await agent_shop(connection, resolved, orchestrator, app.state.model_ref, body.policy_id, body.goal)
        return {
            "chosen": {"sku": result["sku"], "reasoning": result["reasoning"], "model": result["model"]},
            "decision": result["decision"].model_dump(mode="json"),
            "proposal_id": str(result["proposal_id"]),
        }

    @app.post("/v1/policies")
    def create_policy(body: PolicyIn, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=organization_id,
                request_id=request.state.request_id,
            )
            created = policies.create_draft(connection, resolved, body.instruction, drafter=policy_drafter())
        return {"policy": created.model_dump(mode="json")}

    @app.get("/v1/policies")
    def list_policies(request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=organization_id,
                request_id=request.state.request_id,
            )
            rows = policies.list_versions(connection, resolved)
        return {"policies": [row.model_dump(mode="json") for row in rows], "next_cursor": None}

    @app.post("/v1/policies/{version_id}/activate")
    def activate_policy(version_id: UUID, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        key = require_idempotency(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=organization_id,
                request_id=request.state.request_id,
            )
            activated = policies.activate(connection, resolved, version_id, key)
        return {"policy": activated.model_dump(mode="json")}

    def decide_sku(body: DecisionIn, request: Request, organization_id: UUID | None):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=organization_id,
                request_id=request.state.request_id,
            )
            decision, evaluation_id, proposal_id = policies.evaluate_sku(
                connection,
                resolved,
                body.policy_id,
                body.sku,
                suggested_unit_amount_minor=body.suggested_unit_amount_minor,
            )
        trace = []
        if body.suggested_unit_amount_minor is not None:
            trace.append("suggested_unit_amount_minor was ignored. The catalog price was used.")
        return {
            "decision": decision.model_dump(mode="json"),
            "evaluation_id": str(evaluation_id),
            "proposal_id": str(proposal_id),
            "proposal": {
                "sku": body.sku,
                "total_minor": decision.evaluated_amount_minor,
                "cart_hash": decision.cart_hash,
            },
            "trace": trace,
        }

    @app.post("/v1/decisions")
    def decide_route(body: DecisionIn, request: Request, organization_id: UUID | None = Query(default=None)):
        return decide_sku(body, request, organization_id)

    @app.post("/v1/proposals")
    def propose_route(body: DecisionIn, request: Request, organization_id: UUID | None = Query(default=None)):
        return decide_sku(body, request, organization_id)

    @app.post("/v1/approvals")
    def request_approval(body: ApprovalIn, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        key = require_idempotency(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=organization_id,
                request_id=request.state.request_id,
            )
            opened = approvals.request_approval(connection, resolved, body.proposal_id, key)
        return {"approval": opened.model_dump(mode="json")}

    @app.get("/v1/approvals")
    def list_approvals(request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=organization_id,
                request_id=request.state.request_id,
            )
            rows = approvals.list_approvals(connection, resolved)
        return {"approvals": [row.model_dump(mode="json") for row in rows], "next_cursor": None}

    @app.get("/v1/approvals/{approval_id}")
    def read_approval(approval_id: UUID, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=organization_id,
                request_id=request.state.request_id,
            )
            found = approvals.get(connection, resolved, approval_id)
        return {"approval": found.model_dump(mode="json")}

    @app.post("/v1/approvals/{approval_id}/approve")
    def approve_approval(approval_id: UUID, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        key = require_idempotency(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=organization_id,
                request_id=request.state.request_id,
            )
            granted = approvals.approve(connection, resolved, approval_id, key)
        return {"approval": granted.model_dump(mode="json")}

    @app.post("/v1/approvals/{approval_id}/reject")
    def reject_approval(approval_id: UUID, body: RejectIn, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        key = require_idempotency(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=organization_id,
                request_id=request.state.request_id,
            )
            rejected = approvals.reject(connection, resolved, approval_id, body.reason, key)
        return {"approval": rejected.model_dump(mode="json")}

    # ---- commerce (v0.8) ---------------------------------------------------

    def payment_provider():
        if not (os.environ.get("PAYPAL_CLIENT_ID") or "").strip():
            raise EngineError("provider_unconfigured", "No payment provider is configured. Set PAYPAL_CLIENT_ID.", 503)
        return PayPalProvider()

    def commerce_for():
        return CommerceEngine(payment_provider())

    @app.get("/v1/catalog")
    def catalog():
        return {"catalog": list_products()}

    @app.post("/v1/payments")
    async def create_payment(body: PaymentIn, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        key = require_idempotency(request)
        engine = commerce_for()
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(connection, token, organization_id=organization_id, request_id=request.state.request_id)
            transaction = await engine.prepare(connection, resolved, body.proposal_id, body.approval_id, key)
        return {"payment": transaction.model_dump(mode="json")}

    @app.post("/v1/payments/{transaction_id}/authorize")
    async def authorize_payment(transaction_id: UUID, body: AuthorizeTxnIn, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        engine = commerce_for()
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(connection, token, organization_id=organization_id, request_id=request.state.request_id)
            transaction = await engine.authorize(connection, resolved, transaction_id, body.order_id)
        return {"payment": transaction.model_dump(mode="json")}

    @app.post("/v1/payments/{transaction_id}/capture")
    async def capture_payment(transaction_id: UUID, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        engine = commerce_for()
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(connection, token, organization_id=organization_id, request_id=request.state.request_id)
            transaction = await engine.capture(connection, resolved, transaction_id)
        return {"payment": transaction.model_dump(mode="json")}

    @app.post("/v1/payments/{transaction_id}/void")
    async def void_payment(transaction_id: UUID, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        engine = commerce_for()
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(connection, token, organization_id=organization_id, request_id=request.state.request_id)
            transaction = await engine.void(connection, resolved, transaction_id)
        return {"payment": transaction.model_dump(mode="json")}

    @app.post("/v1/payments/{transaction_id}/refund")
    async def refund_payment(transaction_id: UUID, request: Request, body: RefundTxnIn | None = None, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        engine = commerce_for()
        amount = body.amount_minor if body is not None else None
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(connection, token, organization_id=organization_id, request_id=request.state.request_id)
            transaction = await engine.refund(connection, resolved, transaction_id, amount)
        return {"payment": transaction.model_dump(mode="json")}

    @app.get("/v1/payments/{transaction_id}")
    def read_payment(transaction_id: UUID, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(connection, token, organization_id=organization_id, request_id=request.state.request_id)
            engine = CommerceEngine()  # read path needs no provider
            transaction = engine.get(connection, resolved, transaction_id)
            attempts = engine.attempts(connection, resolved, transaction_id)
        return {"payment": transaction.model_dump(mode="json"), "attempts": attempts}

    @app.post("/v1/providers/paypal/webhook")
    async def paypal_webhook(request: Request):
        provider = payment_provider()
        body = await request.body()
        with app.state.engine.begin() as connection:
            result = await handle_webhook(connection, provider, dict(request.headers), body)
        return {"webhook": result}

    # ---- audit, usage, and developer keys (v0.9) ---------------------------

    def resolve_any(connection, token, organization_id, request_id):
        """A Better Auth session, or an `mk_` API key scoped to one organization."""
        if token.startswith("mk_"):
            org = api_keys_store.resolve_key(connection, token)
            if organization_id is not None and organization_id != org:
                raise EngineError("forbidden", "That key is for a different organization.", 403)
            return ExecutionContext(organization_id=org, user_id=None, request_id=request_id, permissions=expand_roles(["developer"]))
        return resolve_execution_context(connection, token, organization_id=organization_id, request_id=request_id)

    @app.get("/v1/timeline")
    def timeline(request: Request, type: str = Query(min_length=1), id: UUID = Query(...), organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_any(connection, token, organization_id, request.state.request_id)
            events = get_timeline(connection, resolved, type, id)
            report = verify_history(connection, resolved, type, id)
        return {"timeline": events, "report": report}

    @app.get("/v1/usage")
    def usage(request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_any(connection, token, organization_id, request.state.request_id)
            summary = read_usage(connection, resolved)
        return {"usage": summary}

    @app.post("/v1/api-keys")
    def create_api_key(body: ApiKeyIn, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(connection, token, organization_id=organization_id, request_id=request.state.request_id)
            created = api_keys_store.create_key(connection, resolved, body.name)
        return {"api_key": created}

    @app.get("/v1/api-keys")
    def list_api_keys(request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(connection, token, organization_id=organization_id, request_id=request.state.request_id)
            keys = api_keys_store.list_keys(connection, resolved)
        return {"api_keys": keys}

    @app.post("/v1/api-keys/{key_id}/revoke")
    def revoke_api_key(key_id: UUID, request: Request, organization_id: UUID | None = Query(default=None)):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(connection, token, organization_id=organization_id, request_id=request.state.request_id)
            result = api_keys_store.revoke_key(connection, resolved, key_id)
        return {"api_key": result}

    return app


app = create_app()
