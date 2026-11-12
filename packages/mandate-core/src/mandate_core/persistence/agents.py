"""Agent definitions and immutable published versions."""

import json
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from mandate_core.contracts import AgentDefinition, AgentVersion, ExecutionContext
from mandate_core.contracts.models import FallbackRef, ModelRef
from mandate_core.errors import EngineError
from mandate_core.persistence.scope import use_tenant_scope

_INSERT_AGENT = text(
    """
    insert into agents.agents (id, organization_id, name, description, graph_kind)
    values (:id, :organization_id, :name, :description, :graph_kind)
    returning id, organization_id, name, description, graph_kind, created_at
    """
)

_LOCK_AGENT = text(
    """
    select id
    from agents.agents
    where id = :agent_id and organization_id = :organization_id
    for update
    """
)

_NEXT_VERSION = text(
    """
    select coalesce(max(version), 0) + 1 as version
    from agents.agent_versions
    where agent_id = :agent_id
    """
)

_INSERT_VERSION = text(
    """
    insert into agents.agent_versions (
      id, organization_id, agent_id, version, provider, model, temperature,
      fallbacks, system_prompt, skill_names, voice_id, published_by
    )
    values (
      :id, :organization_id, :agent_id, :version, :provider, :model, :temperature,
      cast(:fallbacks as jsonb), :system_prompt, cast(:skill_names as jsonb), :voice_id, :published_by
    )
    returning id, organization_id, agent_id, version, provider, model, temperature,
              fallbacks, system_prompt, skill_names, voice_id, published_at, published_by
    """
)

_READ_AGENT = text(
    """
    select id, organization_id, name, description, graph_kind, created_at
    from agents.agents
    where id = :agent_id and organization_id = :organization_id
    """
)

_LIST_AGENTS = text(
    """select id, organization_id, name, description, graph_kind, created_at
       from agents.agents where organization_id = :organization_id order by created_at desc"""
)

_LIST_VERSIONS = text(
    """select id, organization_id, agent_id, version, provider, model, temperature,
              fallbacks, system_prompt, skill_names, voice_id, published_at, published_by
       from agents.agent_versions where organization_id = :organization_id and agent_id = :agent_id
       order by version desc"""
)


def _version(row) -> AgentVersion:
    fallbacks = tuple(FallbackRef.model_validate(item) for item in (row["fallbacks"] or []))
    skill_names = row.get("skill_names") or []
    if isinstance(skill_names, str):
        skill_names = json.loads(skill_names)
    return AgentVersion(
        id=row["id"],
        agent_id=row["agent_id"],
        organization_id=row["organization_id"],
        version=row["version"],
        model=ModelRef(provider=row["provider"], model=row["model"], temperature=row["temperature"]),
        fallbacks=fallbacks,
        system_prompt=row["system_prompt"],
        skill_names=tuple(skill_names),
        voice_id=row.get("voice_id"),
        published_at=row["published_at"],
        published_by=row["published_by"],
    )


class AgentRepository:
    def list_agents(self, connection: Connection, context: ExecutionContext) -> list[AgentDefinition]:
        use_tenant_scope(connection, context.organization_id)
        rows = connection.execute(_LIST_AGENTS, {"organization_id": context.organization_id}).mappings().all()
        return [AgentDefinition.model_validate(dict(row)) for row in rows]

    def create_agent(self, connection: Connection, context: ExecutionContext, name: str, description: str, graph_kind: str) -> AgentDefinition:
        use_tenant_scope(connection, context.organization_id)
        row = connection.execute(
            _INSERT_AGENT,
            {
                "id": uuid4(),
                "organization_id": context.organization_id,
                "name": name,
                "description": description,
                "graph_kind": graph_kind,
            },
        ).mappings().one()
        return AgentDefinition.model_validate(dict(row))

    def get_agent(self, connection: Connection, context: ExecutionContext, agent_id: UUID) -> AgentDefinition:
        use_tenant_scope(connection, context.organization_id)
        row = connection.execute(
            _READ_AGENT,
            {"agent_id": agent_id, "organization_id": context.organization_id},
        ).mappings().first()
        if row is None:
            raise EngineError("not_found", "That agent does not exist.", 404)
        return AgentDefinition.model_validate(dict(row))

    def list_versions(self, connection: Connection, context: ExecutionContext, agent_id: UUID) -> list[dict]:
        use_tenant_scope(connection, context.organization_id)
        if connection.execute(_LOCK_AGENT, {"agent_id": agent_id, "organization_id": context.organization_id}).first() is None:
            raise EngineError("not_found", "That agent does not exist.", 404)
        rows = connection.execute(_LIST_VERSIONS, {"organization_id": context.organization_id, "agent_id": agent_id}).mappings().all()
        versions = []
        for row in rows:
            version = _version(row).model_dump(mode="json")
            names = row["skill_names"] or []
            if isinstance(names, str):
                names = json.loads(names)
            version["skill_names"] = names
            versions.append(version)
        return versions

    def publish_version(
        self,
        connection: Connection,
        context: ExecutionContext,
        agent_id: UUID,
        *,
        provider: str,
        model: str,
        temperature: float,
        system_prompt: str,
        fallbacks: tuple[FallbackRef, ...] = (),
        skill_names: tuple[str, ...] = ("list_products", "propose"),
        voice_id: str | None = None,
    ) -> AgentVersion:
        if context.user_id is None:
            raise EngineError("unauthenticated", "A user is required to publish a version.", 401)
        use_tenant_scope(connection, context.organization_id)
        locked = connection.execute(
            _LOCK_AGENT,
            {"agent_id": agent_id, "organization_id": context.organization_id},
        ).first()
        if locked is None:
            raise EngineError("not_found", "That agent does not exist.", 404)
        version = connection.execute(_NEXT_VERSION, {"agent_id": agent_id}).scalar_one()
        row = connection.execute(
            _INSERT_VERSION,
            {
                "id": uuid4(),
                "organization_id": context.organization_id,
                "agent_id": agent_id,
                "version": version,
                "provider": provider,
                "model": model,
                "temperature": temperature,
                "fallbacks": json.dumps([item.model_dump() for item in fallbacks]),
                "system_prompt": system_prompt,
                "skill_names": json.dumps(list(skill_names)),
                "voice_id": voice_id,
                "published_by": context.user_id,
            },
        ).mappings().one()
        return _version(row)

    def replace_prompt(self, connection: Connection, context: ExecutionContext, version_id: UUID, system_prompt: str) -> None:
        use_tenant_scope(connection, context.organization_id)
        try:
            result = connection.execute(
                text(
                    """
                    update agents.agent_versions
                    set system_prompt = :system_prompt
                    where id = :version_id and organization_id = :organization_id
                    """
                ),
                {
                    "system_prompt": system_prompt,
                    "version_id": version_id,
                    "organization_id": context.organization_id,
                },
            )
        except DBAPIError as exc:
            raise EngineError("version_immutable", "A published version cannot be edited.", 409) from exc
        if result.rowcount == 0:
            raise EngineError("not_found", "That version does not exist.", 404)
        raise EngineError("version_immutable", "A published version cannot be edited.", 409)
