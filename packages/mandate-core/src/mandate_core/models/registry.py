"""Looks up a provider by the name stored on an agent version."""

from mandate_core.errors import EngineError
from mandate_core.models.providers import ModelProvider, OpenAIProvider, StaticProvider
from mandate_core.models.types import ModelCapabilities


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, ModelProvider] = {}

    def register(self, provider: ModelProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> ModelProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise EngineError("model_unavailable", "That model provider is not registered.", 404) from exc

    def catalog(self) -> list[dict]:
        rows = []
        for provider in self._providers.values():
            sample = "gpt-4o-mini" if provider.name == "openai" else "static"
            capabilities: ModelCapabilities = provider.capabilities(sample)
            rows.append({"name": provider.name, "model": sample, "capabilities": capabilities.model_dump()})
        return rows


def default_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(StaticProvider())
    registry.register(OpenAIProvider())
    return registry
