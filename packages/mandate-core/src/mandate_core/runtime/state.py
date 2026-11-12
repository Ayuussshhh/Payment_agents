"""Checkpointed graph state and the trusted context that is rebuilt on resume."""

from dataclasses import dataclass
import os
from operator import add
from typing import Annotated, Any
from uuid import UUID

import httpx

from langgraph.graph.message import add_messages
from typing_extensions import NotRequired, TypedDict

from mandate_core.contracts.context import ExecutionLimits


@dataclass
class SkillCall:
    name: str
    arguments: dict


class SkillPort:
    """In-process skills. PayPal is not a method on this object."""

    def __init__(self, handler=None):
        self.calls: list[SkillCall] = []
        self.handler = handler

    def execute(self, name: str, arguments: dict, graph_context: "GraphContext | None" = None) -> dict:
        self.calls.append(SkillCall(name, arguments))
        if self.handler is not None:
            handled = self.handler(name, arguments, graph_context)
            if handled is not None:
                return handled
        if name == "list_products":
            from mandate_core.skills.catalog import list_products

            return {"products": list_products()}
        if name == "web_search":
            query = str(arguments.get("query", "")).strip()
            if not query or len(query) > 300:
                raise ValueError("Search query must be between 1 and 300 characters.")
            api_key = os.environ.get("TAVILY_API_KEY", "").strip()
            if not api_key:
                raise ValueError("Web research is not configured. Set TAVILY_API_KEY on the engine.")
            try:
                response = httpx.post(
                    "https://api.tavily.com/search",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"query": query, "search_depth": "basic", "max_results": 5, "include_answer": False},
                    timeout=12,
                )
                response.raise_for_status()
                body = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise ValueError("Web search failed. Check the Tavily key and try again.") from exc
            results = [
                {"title": row.get("title", ""), "url": row.get("url", ""), "content": row.get("content", "")[:700]}
                for row in body.get("results", [])[:5]
                if row.get("url", "").startswith(("https://", "http://"))
            ]
            return {"query": query, "results": results}
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
    url: NotRequired[str]


class BuyerState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    proposal_ids: Annotated[list[str], add]
    proposal_results: Annotated[list[dict], add]
    trace: Annotated[list[TraceEvent], add]
    pending_tools: list
    model_calls: int
    stop_reason: str
