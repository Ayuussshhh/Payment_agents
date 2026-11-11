"""Checkpointed graph state and the trusted context that is rebuilt on resume."""

from dataclasses import dataclass
from operator import add
from typing import Annotated, Any
from uuid import UUID

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from mandate_core.contracts.context import ExecutionLimits


@dataclass
class SkillCall:
    name: str
    arguments: dict


class SkillPort:
    """In-process skills. PayPal is not a method on this object."""

    def __init__(self):
        self.calls: list[SkillCall] = []

    def execute(self, name: str, arguments: dict) -> dict:
        self.calls.append(SkillCall(name, arguments))
        return {"proposal_id": f"proposal-{len(self.calls)}", "sku": arguments.get("sku")}


class EventLog:
    def __init__(self):
        self.names: list[str] = []

    def append(self, name: str, payload: dict | None = None) -> None:
        self.names.append(name)


class ModelPort:
    def complete(self, messages: list, tools: tuple, prompt: str) -> Any:
        raise NotImplementedError


@dataclass(frozen=True)
class GraphContext:
    organization_id: UUID
    run_id: UUID
    agent_version_id: UUID
    policy_version_id: UUID | None
    request_id: str
    skill_allowlist: frozenset[str]
    skills: SkillPort
    tools: tuple
    system_prompt: str
    limits: ExecutionLimits
    cancel_requested: bool
    model: ModelPort
    events: EventLog


class TraceEvent(TypedDict):
    agent: str
    text: str


class BuyerState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    proposal_ids: Annotated[list[str], add]
    trace: Annotated[list[TraceEvent], add]
    pending_tools: list
    model_calls: int
    stop_reason: str
