"""In-memory published versions and runs. The SQL store uses the same methods."""

from datetime import datetime, timezone
from uuid import UUID

from mandate_core.contracts import AgentRun, AgentVersion


class MemoryRuntimeStore:
    def __init__(self):
        self.versions: dict[UUID, AgentVersion] = {}
        self.latest: dict[tuple[UUID, UUID], UUID] = {}
        self.agent_names: dict[UUID, str] = {}
        self.skill_names: dict[UUID, tuple[str, ...]] = {}
        self.graph_kinds: dict[UUID, str] = {}
        self.runs: dict[UUID, AgentRun] = {}
        self.members: set[tuple[UUID, UUID]] = set()

    def add_version(self, version: AgentVersion, skill_names: tuple[str, ...], agent_name: str, graph_kind: str = "buyer") -> None:
        self.versions[version.id] = version
        self.latest[(version.organization_id, version.agent_id)] = version.id
        self.agent_names[version.agent_id] = agent_name
        self.skill_names[version.id] = skill_names
        self.graph_kinds[version.agent_id] = graph_kind
        self.members.add((version.organization_id, version.published_by))

    def rename_agent(self, agent_id: UUID, name: str) -> None:
        self.agent_names[agent_id] = name

    def revoke(self, organization_id: UUID, user_id: UUID) -> None:
        self.members.discard((organization_id, user_id))

    def membership_active(self, organization_id: UUID, user_id: UUID | None) -> bool:
        return user_id is not None and (organization_id, user_id) in self.members

    def kind_for(self, agent_id: UUID) -> str:
        return self.graph_kinds.get(agent_id, "buyer")

    def names_for(self, version_id: UUID) -> tuple[str, ...]:
        return self.skill_names.get(version_id, ())

    def get_version(self, organization_id: UUID, version_id: UUID) -> AgentVersion | None:
        version = self.versions.get(version_id)
        if version is None or version.organization_id != organization_id:
            return None
        return version

    def latest_version(self, organization_id: UUID, agent_id: UUID) -> AgentVersion | None:
        version_id = self.latest.get((organization_id, agent_id))
        if version_id is None:
            return None
        return self.versions[version_id]

    def insert_run(self, run: AgentRun) -> None:
        self.runs[run.id] = run

    def save_run(self, run: AgentRun) -> None:
        self.runs[run.id] = run

    def get_run(self, organization_id: UUID, run_id: UUID) -> AgentRun | None:
        run = self.runs.get(run_id)
        if run is None or run.organization_id != organization_id:
            return None
        return run


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
