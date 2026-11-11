"""Provider adapters. The OpenAI key stays inside the adapter."""

import json
import os
from collections.abc import AsyncIterator
from typing import Protocol

import httpx

from mandate_core.errors import EngineError
from mandate_core.models.types import (
    ModelCapabilities,
    ModelEvent,
    ModelRequest,
    ModelResponse,
    ToolCall,
    TransportResult,
)


class ModelProvider(Protocol):
    name: str

    def capabilities(self, model: str) -> ModelCapabilities: ...

    async def invoke(self, request: ModelRequest) -> ModelResponse: ...

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]: ...


class HttpTransport(Protocol):
    async def post(self, url: str, headers: dict, body: dict, stream: bool = False) -> TransportResult: ...


class HttpxTransport:
    async def post(self, url: str, headers: dict, body: dict, stream: bool = False) -> TransportResult:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if stream:
                    lines = []
                    async with client.stream("POST", url, headers=headers, json=body) as response:
                        async for line in response.aiter_lines():
                            lines.append(line)
                        return TransportResult(status=response.status_code, lines=tuple(lines))
                response = await client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise EngineError("provider_error", "The model provider request failed.", 502) from exc
        payload = response.json() if response.content else {}
        return TransportResult(status=response.status_code, body=payload if isinstance(payload, dict) else {})


def _default_openai_capabilities(model: str) -> ModelCapabilities:
    known = {
        "gpt-4o-mini": ModelCapabilities(
            tool_calling=True,
            structured_output=True,
            streaming=True,
            context_window=128_000,
            input_types=("text",),
        )
    }
    return known.get(
        model,
        ModelCapabilities(tool_calling=False, structured_output=False, streaming=True, context_window=8_192),
    )


class StaticProvider:
    """Deterministic provider for tests and for switching without a live key."""

    def __init__(
        self,
        content: str = "static summary",
        fail: bool = False,
        capabilities: ModelCapabilities | None = None,
        name: str = "static",
    ):
        self.name = name
        self.content = content
        self.fail = fail
        self._capabilities = capabilities or ModelCapabilities(
            tool_calling=True,
            structured_output=True,
            streaming=True,
            context_window=8_192,
        )

    def capabilities(self, model: str) -> ModelCapabilities:
        return self._capabilities

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        if self.fail:
            raise EngineError("provider_error", "The static provider was set to fail.", 502)
        return ModelResponse(
            provider=self.name,
            model=request.model,
            content=self.content,
            tool_calls=(ToolCall(name="propose", arguments={"sku": "DELL-LAT-7420"}),),
            input_tokens=4,
            output_tokens=3,
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        response = await self.invoke(request)
        yield ModelEvent(content=response.content, done=True, input_tokens=response.input_tokens, output_tokens=response.output_tokens)


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, transport: HttpTransport | None = None):
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self.base_url = (base_url if base_url is not None else os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.transport = transport or HttpxTransport()

    def capabilities(self, model: str) -> ModelCapabilities:
        return _default_openai_capabilities(model)

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        result = await self._send(request, stream=False)
        message = ((result.body.get("choices") or [{}])[0].get("message") or {})
        usage = result.body.get("usage") or {}
        calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            arguments = function.get("arguments") or "{}"
            if isinstance(arguments, str):
                arguments = json.loads(arguments or "{}")
            calls.append(ToolCall(name=function.get("name") or "", arguments=arguments))
        return ModelResponse(
            provider=self.name,
            model=request.model,
            content=message.get("content") or "",
            tool_calls=tuple(calls),
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        result = await self._send(request, stream=True)
        content = []
        for line in result.lines:
            if not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if data == "[DONE]":
                break
            payload = json.loads(data)
            delta = ((payload.get("choices") or [{}])[0].get("delta") or {}).get("content") or ""
            if delta:
                content.append(delta)
                yield ModelEvent(content=delta)
        yield ModelEvent(content="", done=True)

    async def _send(self, request: ModelRequest, stream: bool) -> TransportResult:
        if not self.api_key:
            raise EngineError("model_unavailable", "No model key is configured.", 503)
        body = {
            "model": request.model,
            "messages": [message.model_dump() for message in request.messages],
            "temperature": request.temperature,
            "stream": stream,
        }
        if request.tools:
            body["tools"] = list(request.tools)
        if request.json_object:
            body["response_format"] = {"type": "json_object"}
        result = await self.transport.post(
            f"{self.base_url}/chat/completions",
            {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            body,
            stream,
        )
        if result.status >= 400:
            raise EngineError("provider_error", "The model provider rejected the request.", 502)
        return result
