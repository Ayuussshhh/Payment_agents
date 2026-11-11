import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from mandate_core.contracts import AgentVersion, ExecutionContext
from mandate_core.contracts.context import ExecutionLimits
from mandate_core.contracts.models import ModelRef
from mandate_core.errors import EngineError
from mandate_core.models.types import ModelResponse, ToolCall
from mandate_core.runtime import AgentRuntime, EventLog, MemoryRuntimeStore, SkillPort, graph_factory


def identity():
    return uuid4(), uuid4(), uuid4()


def published(agent_id, organization_id, user_id, number, prompt):
    return AgentVersion(
        id=uuid4(),
        agent_id=agent_id,
        organization_id=organization_id,
        version=number,
        model=ModelRef(provider="static", model="static"),
        system_prompt=prompt,
        published_at=datetime.now(timezone.utc),
        published_by=user_id,
    )


class ScriptedModel:
    def __init__(self, steps):
        self.steps = list(steps)
        self.prompts = []

    def complete(self, messages, tools, prompt):
        self.prompts.append(prompt)
        return self.steps.pop(0)


def tool_step():
    return ModelResponse(provider="static", model="static", content="", tool_calls=(ToolCall(name="propose", arguments={"sku": "DELL-LAT-7420"}),))


def done_step():
    return ModelResponse(provider="static", model="static", content="done")


def runtime(limits=None):
    store = MemoryRuntimeStore()
    skills = SkillPort()
    events = EventLog()
    engine = AgentRuntime(store, InMemorySaver(), skills, events)
    return store, skills, events, engine, limits or ExecutionLimits()


def test_buyer_tools_are_the_attached_skills_and_exclude_paypal():
    built = graph_factory("buyer", ("propose", "paypal"), InMemorySaver())
    names = [tool["function"]["name"] for tool in built.tools]
    assert names == ["propose"]
    assert "price" not in built.tools[0]["function"]["parameters"]["properties"]
    assert graph_factory("compiler", ("propose",), InMemorySaver()).tools == ()


def test_run_uses_the_published_prompt_after_the_agent_is_renamed():
    organization_id, agent_id, user_id = identity()
    store, _skills, _events, engine, limits = runtime()
    first = published(agent_id, organization_id, user_id, 1, "first prompt")
    second = published(agent_id, organization_id, user_id, 2, "second prompt")
    store.add_version(first, (), "Buyer")
    store.add_version(second, (), "Buyer")
    store.rename_agent(agent_id, "Renamed buyer")
    context = ExecutionContext(organization_id=organization_id, user_id=user_id, request_id="req_run", limits=limits)

    async def scenario():
        with pytest.raises(EngineError) as missing:
            empty = MemoryRuntimeStore()
            await AgentRuntime(empty, InMemorySaver()).create_run(context, agent_id, None, {})
        assert missing.value.code == "not_found"
        run = await engine.create_run(context, agent_id, None, {"goal": "laptop"}, ScriptedModel([done_step()]))
        return run

    run = asyncio.run(scenario())
    assert run.agent_version_id == second.id
    assert run.output["system_prompt"] == "second prompt"
    assert engine._config(run.id)["configurable"]["thread_id"] == str(run.id)


def test_resume_keeps_the_skill_result_and_does_not_call_it_again():
    organization_id, agent_id, user_id = identity()
    store, skills, events, engine, limits = runtime()
    version = published(agent_id, organization_id, user_id, 1, "buyer prompt")
    store.add_version(version, ("propose",), "Buyer")
    context = ExecutionContext(organization_id=organization_id, user_id=user_id, request_id="req_resume", limits=limits)
    model = ScriptedModel([tool_step(), done_step()])

    async def scenario():
        paused = await engine.create_run(context, agent_id, version.id, {}, model, interrupt_after=("tools",))
        assert paused.status == "running"
        assert paused.output["proposal_ids"]
        resumed = await engine.resume_run(context, paused.id, None, model)
        return paused, resumed

    paused, resumed = asyncio.run(scenario())
    assert len(skills.calls) == 1
    assert skills.calls[0].name == "propose"
    assert resumed.status == "succeeded"
    assert resumed.output["proposal_ids"] == paused.output["proposal_ids"]
    assert "model.invoked" in events.names
    assert "skill.executed" in events.names


def test_revoked_membership_blocks_resume():
    organization_id, agent_id, user_id = identity()
    store, skills, _events, engine, limits = runtime()
    version = published(agent_id, organization_id, user_id, 1, "buyer prompt")
    store.add_version(version, ("propose",), "Buyer")
    context = ExecutionContext(organization_id=organization_id, user_id=user_id, request_id="req_revoke", limits=limits)

    async def scenario():
        paused = await engine.create_run(
            context, agent_id, version.id, {}, ScriptedModel([tool_step(), done_step()]), interrupt_after=("tools",)
        )
        store.revoke(organization_id, user_id)
        with pytest.raises(EngineError) as caught:
            await engine.resume_run(context, paused.id, None, ScriptedModel([done_step()]))
        assert caught.value.code == "not_found"
        return paused

    paused = asyncio.run(scenario())
    assert len(skills.calls) == 1
    assert engine.store.get_run(organization_id, paused.id).output["proposal_ids"]


def test_limits_and_cancel_keep_the_proposal():
    organization_id, agent_id, user_id = identity()
    store, skills, events, engine, _limits = runtime(ExecutionLimits(max_model_calls=1))
    version = published(agent_id, organization_id, user_id, 1, "buyer prompt")
    store.add_version(version, ("propose",), "Buyer")
    context = ExecutionContext(
        organization_id=organization_id,
        user_id=user_id,
        request_id="req_limit",
        limits=ExecutionLimits(max_model_calls=1),
    )

    async def limited():
        return await engine.create_run(context, agent_id, version.id, {}, ScriptedModel([tool_step(), done_step()]))

    limited_run = asyncio.run(limited())
    assert limited_run.status == "limited"
    assert "agent.run.limited" in events.names

    store.members.add((organization_id, user_id))
    context = ExecutionContext(organization_id=organization_id, user_id=user_id, request_id="req_cancel", limits=ExecutionLimits())
    model = ScriptedModel([tool_step(), done_step()])

    async def cancelled():
        paused = await engine.create_run(context, agent_id, version.id, {}, model, interrupt_after=("tools",))
        proposal = paused.output["proposal_ids"][0]
        stopped = await engine.cancel_run(context, paused.id, model)
        return proposal, stopped

    proposal, stopped = asyncio.run(cancelled())
    assert stopped.status == "cancelled"
    assert proposal in stopped.output["proposal_ids"]
    assert len(skills.calls) == 2
