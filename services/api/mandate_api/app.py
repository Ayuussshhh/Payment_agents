"""Mandate platform API. This process calls the engine. It does not own policy or payment rules."""

import os
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from mandate_core import __version__
from mandate_core.settings import database_url as configured_database_url
from mandate_core.errors import EngineError
from mandate_core.identity import resolve_execution_context
from mandate_core.models import default_registry
from mandate_core.skills import SkillRuntime
from mandate_core.persistence.agents import AgentRepository
from mandate_core.runtime import AgentRuntime
from mandate_core.runtime.sql_store import SqlRuntimeStore
from langgraph.checkpoint.memory import InMemorySaver

RESOURCES = [
    {"method": "GET", "path": "/health", "purpose": "Process, database, and Redis connectivity."},
    {"method": "GET", "path": "/v1", "purpose": "Engine name, package version, and this resource list."},
    {"method": "GET", "path": "/v1/context", "purpose": "Resolve a session into an execution context."},
    {"method": "POST", "path": "/v1/agents", "purpose": "Create an agent definition."},
    {"method": "GET", "path": "/v1/agents/{id}", "purpose": "Read one agent in the caller's organization."},
    {"method": "POST", "path": "/v1/agents/{id}/versions", "purpose": "Publish an immutable agent version."},
    {"method": "POST", "path": "/v1/agents/{id}/runs", "purpose": "Run a published agent version."},
    {"method": "POST", "path": "/v1/runs/{id}/resume", "purpose": "Resume a paused run."},
    {"method": "POST", "path": "/v1/runs/{id}/cancel", "purpose": "Stop a run at the next step. Does not void a payment."},
    {"method": "GET", "path": "/v1/runs/{id}", "purpose": "Read a run, its trace, and its proposal ids."},
    {"method": "GET", "path": "/v1/models", "purpose": "Provider names and capability metadata. No secrets."},
    {"method": "GET", "path": "/v1/skills", "purpose": "Skills that can be attached. PayPal is not a skill."},
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
        return AgentRuntime(SqlRuntimeStore(connection), app.state.checkpointer)

    @app.post("/v1/agents/{agent_id}/runs")
    async def start_run(agent_id: UUID, request: Request):
        token = require_session(request)
        with app.state.engine.begin() as connection:
            resolved = resolve_execution_context(
                connection,
                token,
                organization_id=None,
                request_id=request.state.request_id,
            )
            run = await runtime_for(connection).create_run(resolved, agent_id, None, {})
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

    return app


app = create_app()
