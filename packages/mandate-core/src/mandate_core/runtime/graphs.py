"""Buyer and compiler graphs. Tools come from the published version."""

from dataclasses import dataclass

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from mandate_core.runtime.state import BuyerState, GraphContext
from mandate_core.runtime.tools import tool_definitions


def model_node(state: BuyerState, runtime: Runtime[GraphContext]):
    context = runtime.context
    if context.cancel_requested:
        context.events.append("agent.run.cancelled")
        return {"stop_reason": "cancelled", "pending_tools": [], "trace": [{"agent": "buyer", "text": "Run cancelled."}]}
    calls = state.get("model_calls", 0)
    if calls >= context.limits.max_model_calls:
        context.events.append("agent.run.limited")
        return {"stop_reason": "limited", "pending_tools": [], "trace": [{"agent": "buyer", "text": "Model call limit reached."}]}
    response = context.model.complete(list(state.get("messages") or []), context.tools, context.system_prompt)
    context.events.append("model.invoked")
    pending = [{"name": call.name, "arguments": call.arguments} for call in response.tool_calls]
    trace = [{"agent": "buyer", "text": "Model returned " + (pending[0]["name"] if pending else "a final answer") + "."}]
    update = {
        "model_calls": calls + 1,
        "pending_tools": pending,
        "trace": trace,
        "messages": [{"role": "assistant", "content": response.content or ""}],
    }
    if not pending:
        update["stop_reason"] = "completed"
        context.events.append("agent.run.completed")
    return update


def tool_node(state: BuyerState, runtime: Runtime[GraphContext]):
    context = runtime.context
    proposals = []
    trace = []
    for call in state.get("pending_tools") or []:
        name = call["name"]
        if name.lower() == "paypal" or name not in context.skill_allowlist:
            trace.append({"agent": "buyer", "text": "Blocked skill " + name + "."})
            continue
        result = context.skills.execute(name, call.get("arguments") or {})
        context.events.append("skill.executed")
        if result.get("proposal_id"):
            proposals.append(result["proposal_id"])
        trace.append({"agent": "buyer", "text": name + " executed."})
    return {"proposal_ids": proposals, "trace": trace, "pending_tools": []}


def route(state: BuyerState) -> str:
    if state.get("stop_reason") in {"cancelled", "limited", "completed"}:
        return "end"
    if state.get("pending_tools"):
        return "tools"
    return "end"


def build_buyer_graph(checkpointer):
    builder = StateGraph(BuyerState, context_schema=GraphContext)
    builder.add_node("model", model_node)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "model")
    builder.add_conditional_edges("model", route, {"tools": "tools", "end": END})
    builder.add_edge("tools", "model")
    return builder.compile(checkpointer=checkpointer)


def compiler_node(state: BuyerState, runtime: Runtime[GraphContext]):
    runtime.context.events.append("agent.run.completed")
    return {"stop_reason": "completed", "trace": [{"agent": "compiler", "text": "Draft only. No tools."}]}


def build_compiler_graph(checkpointer):
    builder = StateGraph(BuyerState, context_schema=GraphContext)
    builder.add_node("compiler", compiler_node)
    builder.add_edge(START, "compiler")
    builder.add_edge("compiler", END)
    return builder.compile(checkpointer=checkpointer)


@dataclass(frozen=True)
class BuiltGraph:
    graph: object
    tools: tuple
    graph_kind: str


def graph_factory(graph_kind: str, skill_names: tuple[str, ...], checkpointer) -> BuiltGraph:
    if graph_kind == "compiler":
        return BuiltGraph(build_compiler_graph(checkpointer), (), "compiler")
    tools = tool_definitions(skill_names)
    return BuiltGraph(build_buyer_graph(checkpointer), tools, "buyer")
