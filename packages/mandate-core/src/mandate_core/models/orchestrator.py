"""Choose a provider, validate structured output, and record usage."""

from pydantic import BaseModel, ValidationError

from mandate_core.contracts import ExecutionContext
from mandate_core.contracts.models import FallbackRef
from mandate_core.errors import EngineError
from mandate_core.models.registry import ProviderRegistry
from mandate_core.models.types import ModelRequest, ModelResponse, TokenUsage
from mandate_core.models.usage import MemoryUsage, UsageWriter


class ModelOrchestrator:
    def __init__(self, registry: ProviderRegistry, usage: UsageWriter | None = None):
        self.registry = registry
        self.usage = usage if usage is not None else MemoryUsage()

    async def invoke_model(
        self,
        context: ExecutionContext,
        request: ModelRequest,
        output_model: type[BaseModel] | None = None,
        fallback: FallbackRef | None = None,
    ) -> ModelResponse:
        response = await self._invoke_with_fallback(request, fallback)
        if output_model is not None:
            try:
                output_model.model_validate_json(response.content)
            except ValidationError as exc:
                raise EngineError("model_output_invalid", exc.errors()[0]["msg"], 422) from exc
        self.usage.record(
            TokenUsage(
                organization_id=context.organization_id,
                run_id=context.run_id,
                provider=response.provider,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
        )
        return response

    async def stream_model(self, context: ExecutionContext, request: ModelRequest):
        provider = self.registry.get(request.provider)
        async for event in provider.stream(request):
            yield event

    async def get_model_config(self, context: ExecutionContext, provider: str, model: str):
        return self.registry.get(provider).capabilities(model)

    async def _invoke_with_fallback(self, request: ModelRequest, fallback: FallbackRef | None) -> ModelResponse:
        provider = self.registry.get(request.provider)
        try:
            return await provider.invoke(request)
        except EngineError as exc:
            if exc.code != "provider_error" or fallback is None:
                raise
            replacement = self.registry.get(fallback.model.provider)
            capabilities = replacement.capabilities(fallback.model.model)
            available = {
                "tool_calling": capabilities.tool_calling,
                "structured_output": capabilities.structured_output,
                "streaming": capabilities.streaming,
            }
            missing = [name for name in fallback.required_capabilities if not available.get(name, False)]
            if missing:
                raise EngineError("model_unavailable", "The fallback model lacks a required capability.", 503) from exc
            switched = request.model_copy(
                update={"provider": fallback.model.provider, "model": fallback.model.model, "temperature": fallback.model.temperature}
            )
            return await replacement.invoke(switched)
