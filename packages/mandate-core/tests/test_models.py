import asyncio
import json
from uuid import uuid4

import pytest

from mandate_core.contracts import ExecutionContext, PolicyDraft
from mandate_core.contracts.models import FallbackRef, ModelRef
from mandate_core.errors import EngineError
from mandate_core.models import MemoryUsage, ModelOrchestrator, OpenAIProvider, ProviderRegistry, StaticProvider
from mandate_core.models.providers import HttpxTransport
from mandate_core.models.types import ModelCapabilities, ModelMessage, ModelRequest, TransportResult


def context():
    return ExecutionContext(organization_id=uuid4(), user_id=uuid4(), request_id="req_model")


def request(provider: str, content: str = "summarize this SKU", model: str = "gpt-4o-mini") -> ModelRequest:
    return ModelRequest(provider=provider, model=model, messages=(ModelMessage(role="user", content=content),))


class RecordingTransport:
    def __init__(self, body=None, lines=()):
        self.calls = []
        self.body = body or {
            "choices": [{"message": {"content": "A laptop.", "tool_calls": []}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        }
        self.lines = lines

    async def post(self, url, headers, body, stream=False):
        self.calls.append({"url": url, "headers": headers, "body": body, "stream": stream})
        return TransportResult(status=200, body=self.body, lines=tuple(self.lines))


def registry_with(*providers) -> ProviderRegistry:
    found = ProviderRegistry()
    for provider in providers:
        found.register(provider)
    return found


def test_registry_resolves_static_and_openai_as_different_classes():
    found = registry_with(StaticProvider(), OpenAIProvider(api_key=""))
    assert type(found.get("static")) is StaticProvider
    assert type(found.get("openai")) is OpenAIProvider


def test_missing_key_does_not_call_the_network():
    transport = RecordingTransport()

    async def scenario():
        provider = OpenAIProvider(api_key="", transport=transport)
        with pytest.raises(EngineError) as caught:
            await provider.invoke(request("openai"))
        assert caught.value.code == "model_unavailable"
        with pytest.raises(EngineError):
            async for _event in provider.stream(request("openai")):
                pass

    asyncio.run(scenario())
    assert transport.calls == []


def test_openai_transport_receives_the_chat_request_and_hides_the_key():
    transport = RecordingTransport()
    secret = "sk-test-secret"

    async def scenario():
        provider = OpenAIProvider(api_key=secret, base_url="https://example.test/v1", transport=transport)
        response = await provider.invoke(request("openai"))
        assert response.content == "A laptop."
        assert secret not in response.model_dump_json()
        assert isinstance(provider.transport, RecordingTransport)

    asyncio.run(scenario())
    call = transport.calls[0]
    assert call["url"] == "https://example.test/v1/chat/completions"
    assert call["headers"]["Authorization"] == f"Bearer {secret}"
    assert call["body"]["messages"] == [{"role": "user", "content": "summarize this SKU"}]
    assert call["body"]["model"] == "gpt-4o-mini"
    assert call["stream"] is False


def _draft(status=None, drop=None):
    payload = {
        "currency": "USD",
        "maximum_total_minor": 80000,
        "amount_includes": ["tax"],
        "allowed_brands": ["Dell"],
        "required_specs": {"ram_gb_min": 16, "storage_gb_min": 512, "storage_type": "ssd"},
        "forbidden_addon_types": ["warranty"],
        "max_executions": 1,
        "approval_required": True,
        "preferences": ["good battery life"],
        "ambiguities": [],
        "original_instruction": "Order a Dell.",
    }
    if drop:
        payload.pop(drop)
    if status is not None:
        payload["status"] = status
    return json.dumps(payload)


def test_structured_output_rejects_extra_and_missing_fields():
    usage = MemoryUsage()
    found = registry_with(StaticProvider(content=_draft(status="active")))
    orchestrator = ModelOrchestrator(found, usage)

    async def extra():
        with pytest.raises(EngineError) as caught:
            await orchestrator.invoke_model(context(), request("static"), output_model=PolicyDraft)
        assert caught.value.code == "model_output_invalid"

    asyncio.run(extra())
    found.register(StaticProvider(content=_draft(drop="currency")))
    asyncio.run(extra())
    assert usage.rows == []


def test_static_usage_is_recorded_and_a_failure_is_not():
    usage = MemoryUsage()
    found = registry_with(StaticProvider())
    orchestrator = ModelOrchestrator(found, usage)

    async def scenario():
        response = await orchestrator.invoke_model(context(), request("static"))
        assert response.tool_calls[0].name == "propose"
        found.register(StaticProvider(fail=True))
        with pytest.raises(EngineError) as caught:
            await orchestrator.invoke_model(context(), request("static"))
        assert caught.value.code == "provider_error"

    asyncio.run(scenario())
    assert len(usage.rows) == 1
    assert usage.rows[0].provider == "static"
    assert usage.rows[0].input_tokens == 4
    assert usage.rows[0].output_tokens == 3


def test_fallback_runs_only_when_capabilities_match():
    usage = MemoryUsage()
    capable = ModelCapabilities(tool_calling=True, structured_output=True, streaming=True, context_window=8_192)
    weak = ModelCapabilities(tool_calling=False, structured_output=False, streaming=True, context_window=1_024)
    found = registry_with(
        StaticProvider(name="primary", fail=True),
        StaticProvider(name="backup", content="fallback summary", capabilities=capable),
        StaticProvider(name="weak", capabilities=weak),
    )
    orchestrator = ModelOrchestrator(found, usage)
    allowed = FallbackRef(model=ModelRef(provider="backup", model="backup", temperature=0), required_capabilities=("tool_calling",))
    refused = FallbackRef(model=ModelRef(provider="weak", model="weak", temperature=0), required_capabilities=("tool_calling",))

    async def scenario():
        response = await orchestrator.invoke_model(context(), request("primary"), fallback=allowed)
        assert response.content == "fallback summary"
        assert response.provider == "backup"
        with pytest.raises(EngineError) as caught:
            await orchestrator.invoke_model(context(), request("primary"), fallback=refused)
        assert caught.value.code == "model_unavailable"

    asyncio.run(scenario())
    assert [row.provider for row in usage.rows] == ["backup"]


def test_one_caller_switches_provider_without_changing_business_logic():
    transport = RecordingTransport()
    found = registry_with(StaticProvider(), OpenAIProvider(api_key="sk-test-secret", transport=transport))
    orchestrator = ModelOrchestrator(found, MemoryUsage())

    async def summarize(provider_name: str):
        return await orchestrator.invoke_model(context(), request(provider_name))

    async def scenario():
        static_response = await summarize("static")
        openai_response = await summarize("openai")
        assert static_response.content == "static summary"
        assert openai_response.content == "A laptop."

    asyncio.run(scenario())
    assert transport.calls[0]["body"]["messages"][0]["content"] == "summarize this SKU"
    assert not isinstance(found.get("openai").transport, HttpxTransport)
