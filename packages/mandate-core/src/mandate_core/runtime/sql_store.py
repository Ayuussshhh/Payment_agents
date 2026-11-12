"""PostgreSQL run store. It uses the same methods as the in-memory store."""

import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mandate_core.contracts import AgentRun, AgentVersion
from mandate_core.contracts.models import ModelRef
from mandate_core.persistence.scope import use_tenant_scope


def _dump(value) -> str:
    return json.dumps(value)


class SqlRuntimeStore:
    def __init__(self, connection: Connection):
        self.connection = connection

    def kind_for(self, agent_id: UUID) -> str:
        row = self.connection.execute(
            text("select graph_kind from agents.agents where id = :id"),
            {"id": agent_id},
        ).first()
        return row[0] if row else "buyer"

    def names_for(self, version_id: UUID) -> tuple[str, ...]:
        value = self.connection.execute(
            text("select skill_names from agents.agent_versions where id = :id"),
            {"id": version_id},
        ).scalar()
        return tuple(value or ())

    def membership_active(self, organization_id: UUID, user_id: UUID | None) -> bool:
        if user_id is None:
            return False
        use_tenant_scope(self.connection, organization_id)
        row = self.connection.execute(
            text(
                """
                select 1 from identity.memberships
                where organization_id = :organization_id and user_id = :user_id
                """
            ),
            {"organization_id": organization_id, "user_id": user_id},
        ).first()
        return row is not None

    def get_version(self, organization_id: UUID, version_id: UUID) -> AgentVersion | None:
        use_tenant_scope(self.connection, organization_id)
        row = self.connection.execute(
            text(
                """
                select id, agent_id, organization_id, version, provider, model, temperature,
                       system_prompt, skill_names, voice_id, published_at, published_by
                from agents.agent_versions
                where id = :id and organization_id = :organization_id
                """
            ),
            {"id": version_id, "organization_id": organization_id},
        ).mappings().first()
        return _version(row) if row else None

    def latest_version(self, organization_id: UUID, agent_id: UUID) -> AgentVersion | None:
        use_tenant_scope(self.connection, organization_id)
        row = self.connection.execute(
            text(
                """
                select id, agent_id, organization_id, version, provider, model, temperature,
                       system_prompt, skill_names, voice_id, published_at, published_by
                from agents.agent_versions
                where organization_id = :organization_id and agent_id = :agent_id
                order by version desc
                limit 1
                """
            ),
            {"organization_id": organization_id, "agent_id": agent_id},
        ).mappings().first()
        return _version(row) if row else None

    def insert_run(self, run: AgentRun) -> None:
        use_tenant_scope(self.connection, run.organization_id)
        self.connection.execute(
            text(
                """
                insert into agents.agent_runs (
                  id, organization_id, agent_version_id, policy_version_id, status,
                  cancel_requested, input, output, stop_reason, created_at
                )
                values (
                  :id, :organization_id, :agent_version_id, :policy_version_id, :status,
                  :cancel_requested, cast(:input as jsonb), cast(:output as jsonb), :stop_reason, :created_at
                )
                """
            ),
            _run_params(run),
        )

    def save_run(self, run: AgentRun) -> None:
        use_tenant_scope(self.connection, run.organization_id)
        self.connection.execute(
            text(
                """
                update agents.agent_runs
                set status = :status,
                    cancel_requested = :cancel_requested,
                    output = cast(:output as jsonb),
                    stop_reason = :stop_reason,
                    finished_at = :finished_at
                where id = :id and organization_id = :organization_id
                """
            ),
            _run_params(run),
        )

    def get_run(self, organization_id: UUID, run_id: UUID) -> AgentRun | None:
        use_tenant_scope(self.connection, organization_id)
        row = self.connection.execute(
            text(
                """
                select id, organization_id, agent_version_id, policy_version_id, status,
                       cancel_requested, input, output, stop_reason, created_at, finished_at
                from agents.agent_runs
                where id = :id and organization_id = :organization_id
                """
            ),
            {"id": run_id, "organization_id": organization_id},
        ).mappings().first()
        if row is None:
            return None
        return AgentRun(
            id=row["id"],
            organization_id=row["organization_id"],
            agent_version_id=row["agent_version_id"],
            policy_version_id=row["policy_version_id"],
            status=row["status"],
            input=row["input"] or {},
            output=row["output"] or {},
            stop_reason=row["stop_reason"] or "",
            created_at=row["created_at"],
            finished_at=row["finished_at"],
            cancel_requested=row["cancel_requested"],
        )


def _version(row) -> AgentVersion:
    skill_names = row.get("skill_names") or []
    if isinstance(skill_names, str):
        skill_names = json.loads(skill_names)
    return AgentVersion(
        id=row["id"],
        agent_id=row["agent_id"],
        organization_id=row["organization_id"],
        version=row["version"],
        model=ModelRef(provider=row["provider"], model=row["model"], temperature=row["temperature"]),
        system_prompt=row["system_prompt"],
        skill_names=tuple(skill_names),
        voice_id=row.get("voice_id"),
        published_at=row["published_at"],
        published_by=row["published_by"],
    )


def _run_params(run: AgentRun) -> dict:
    return {
        "id": run.id,
        "organization_id": run.organization_id,
        "agent_version_id": run.agent_version_id,
        "policy_version_id": run.policy_version_id,
        "status": run.status,
        "cancel_requested": run.cancel_requested,
        "input": _dump(run.input),
        "output": _dump(run.output),
        "stop_reason": run.stop_reason,
        "created_at": run.created_at or datetime.now(timezone.utc),
        "finished_at": run.finished_at,
    }
