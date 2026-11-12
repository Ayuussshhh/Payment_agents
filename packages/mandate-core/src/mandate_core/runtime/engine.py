"""Execute a published agent version. Resume rebuilds authority from the store."""

from uuid import UUID, uuid4

from mandate_core.contracts import AgentRun, ExecutionContext
from mandate_core.errors import EngineError
from mandate_core.runtime.graphs import graph_factory
from mandate_core.runtime.state import EventLog, GraphContext, ModelPort, SkillPort
from mandate_core.runtime.store import MemoryRuntimeStore, utcnow
from mandate_core.runtime.tools import tool_definitions

STATUS = {
    "completed": "succeeded",
    "limited": "limited",
    "cancelled": "cancelled",
}


class AgentRuntime:
    def __init__(self, store: MemoryRuntimeStore, checkpointer, skills: SkillPort | None = None, events: EventLog | None = None, model_factory=None):
        self.store = store
        self.checkpointer = checkpointer
        self.skills = skills or SkillPort()
        self.events = events or EventLog()
        self.model_factory = model_factory
        self.graphs = {
            "buyer": graph_factory("buyer", (), checkpointer).graph,
            "compiler": graph_factory("compiler", (), checkpointer).graph,
        }

    async def create_run(
        self,
        context: ExecutionContext,
        agent_id: UUID,
        version_id: UUID | None,
        run_input: dict,
        model: ModelPort | None = None,
        interrupt_after: tuple[str, ...] | None = None,
    ) -> AgentRun:
        version = self._resolve(context, agent_id, version_id)
        if not self.store.membership_active(context.organization_id, context.user_id):
            raise EngineError("not_found", "That membership is no longer active.", 404)
        run = AgentRun(
            id=uuid4(),
            organization_id=context.organization_id,
            agent_version_id=version.id,
            status="running",
            input=run_input,
            output={"system_prompt": version.system_prompt, "proposal_ids": [], "trace": []},
            created_at=utcnow(),
        )
        self.store.insert_run(run)
        self.events.append("agent.run.started")
        return self._invoke(context, run, version, model, interrupt_after)

    async def resume_run(self, context: ExecutionContext, run_id: UUID, resume_input: dict | None = None, model: ModelPort | None = None) -> AgentRun:
        run = self._load(context, run_id)
        if not self.store.membership_active(context.organization_id, context.user_id):
            raise EngineError("not_found", "That membership is no longer active.", 404)
        version = self.store.get_version(context.organization_id, run.agent_version_id)
        if version is None:
            raise EngineError("not_found", "That published version does not exist.", 404)
        return self._invoke(context, run, version, model, None)

    async def cancel_run(self, context: ExecutionContext, run_id: UUID, model: ModelPort | None = None) -> AgentRun:
        run = self._load(context, run_id)
        run.cancel_requested = True
        self.store.save_run(run)
        version = self.store.get_version(context.organization_id, run.agent_version_id)
        if version is None:
            raise EngineError("not_found", "That published version does not exist.", 404)
        snapshot = self._graph(version).get_state(self._config(run.id))
        if snapshot is not None and snapshot.next:
            return self._invoke(context, run, version, model, None)
        run.status = "cancelled"
        run.stop_reason = "cancelled"
        run.finished_at = utcnow()
        self.store.save_run(run)
        return run

    async def get_run(self, context: ExecutionContext, run_id: UUID) -> AgentRun:
        return self._load(context, run_id)

    def tools_for(self, graph_kind: str, skill_names: tuple[str, ...]) -> tuple:
        if graph_kind == "compiler":
            return ()
        return tool_definitions(skill_names)

    def _resolve(self, context: ExecutionContext, agent_id: UUID, version_id: UUID | None):
        if version_id is None:
            version = self.store.latest_version(context.organization_id, agent_id)
        else:
            version = self.store.get_version(context.organization_id, version_id)
        if version is None:
            raise EngineError("not_found", "That agent has no published version.", 404)
        return version

    def _load(self, context: ExecutionContext, run_id: UUID) -> AgentRun:
        run = self.store.get_run(context.organization_id, run_id)
        if run is None:
            raise EngineError("not_found", "That run does not exist.", 404)
        return run

    def _graph(self, version):
        kind = self.store.kind_for(version.agent_id)
        return self.graphs[kind]

    def _config(self, run_id: UUID) -> dict:
        return {"configurable": {"thread_id": str(run_id)}}

    def _resolve_model(self, context: ExecutionContext, run: AgentRun, version, model: ModelPort | None) -> ModelPort:
        if model is not None:
            return model
        if self.model_factory is not None:
            return self.model_factory(context, run, version)
        raise EngineError("model_unavailable", "No model is configured for this run.", 503)

    def _context(self, context: ExecutionContext, run: AgentRun, version, model: ModelPort | None) -> GraphContext:
        names = self.store.names_for(version.id)
        kind = self.store.kind_for(version.agent_id)
        tools = () if kind == "compiler" else self.tools_for(kind, names)
        return GraphContext(
            organization_id=context.organization_id,
            run_id=run.id,
            agent_version_id=version.id,
            policy_version_id=context.policy_version_id,
            request_id=context.request_id,
            skill_allowlist=frozenset(names),
            skills=self.skills,
            tools=tools,
            system_prompt=version.system_prompt,
            limits=context.limits,
            cancel_requested=run.cancel_requested,
            model=self._resolve_model(context, run, version, model),
            events=self.events,
        )

    def _invoke(self, context, run: AgentRun, version, model, interrupt_after) -> AgentRun:
        graph = self._graph(version)
        config = self._config(run.id)
        graph_context = self._context(context, run, version, model)
        payload = None if graph.get_state(config).next else {"messages": [{"role": "user", "content": str(run.input)}]}
        kwargs = {"context": graph_context}
        if interrupt_after:
            kwargs["interrupt_after"] = list(interrupt_after)
        state = graph.invoke(payload, config, **kwargs)
        paused = bool(graph.get_state(config).next)
        stop_reason = state.get("stop_reason") or ("paused" if paused else "completed")
        proposals = list(state.get("proposal_ids") or [])
        trace = [_plain_trace(item) for item in state.get("trace") or []]
        run.output = {"system_prompt": version.system_prompt, "proposal_ids": proposals, "trace": trace}
        run.stop_reason = stop_reason
        if paused and not run.cancel_requested:
            run.status = "running"
        else:
            run.status = STATUS.get(stop_reason, "failed")
            run.finished_at = utcnow()
        self.store.save_run(run)
        return run


def _plain_trace(item) -> dict:
    if isinstance(item, dict):
        return {"agent": item.get("agent", "buyer"), "text": item.get("text", "")}
    return {"agent": "buyer", "text": str(item)}
