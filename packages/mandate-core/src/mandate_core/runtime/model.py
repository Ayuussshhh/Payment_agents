"""The model a published agent version actually calls during a run.

The buyer graph node calls ``model.complete(messages, tools, prompt)`` and reads
``.content`` and ``.tool_calls`` off the result. This adapter turns that into a
real provider request, runs it to completion from the synchronous graph, and
records token usage on the request's own connection.
"""

from uuid import UUID

from mandate_core.contracts import AgentVersion, ExecutionContext
from mandate_core.models.registry import ProviderRegistry
from mandate_core.models.sync import run_sync
from mandate_core.models.types import ModelMessage, ModelRequest, ModelResponse, TokenUsage
from mandate_core.models.usage import MemoryUsage, UsageWriter
from mandate_core.runtime.state import ModelPort

_ROLES = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}


def _message(item) -> ModelMessage:
    if isinstance(item, dict):
        role = item.get("role") or item.get("type")
        content = item.get("content", "")
    else:
        role = getattr(item, "role", None) or getattr(item, "type", None)
        content = getattr(item, "content", "")
    role = _ROLES.get(role, role)
    if role not in {"system", "user", "assistant", "tool"}:
        role = "user"
    if not isinstance(content, str):
        content = str(content)
    return ModelMessage(role=role, content=content)


class OrchestratedModel(ModelPort):
    """Calls one provider for one run and writes a usage row per call."""

    def __init__(
        self,
        registry: ProviderRegistry,
        context: ExecutionContext,
        version: AgentVersion,
        run_id: UUID,
        usage: UsageWriter | None = None,
    ):
        self.registry = registry
        self.context = context
        self.version = version
        self.run_id = run_id
        self.usage = usage if usage is not None else MemoryUsage()

    def complete(self, messages: list, tools: tuple, prompt: str) -> ModelResponse:
        provider = self.registry.get(self.version.model.provider)
        request = ModelRequest(
            provider=self.version.model.provider,
            model=self.version.model.model,
            messages=(ModelMessage(role="system", content=prompt), *[_message(item) for item in messages]),
            tools=tuple(tools),
            temperature=self.version.model.temperature,
        )
        response = run_sync(provider.invoke(request))
        self.usage.record(
            TokenUsage(
                organization_id=self.context.organization_id,
                run_id=self.run_id,
                provider=response.provider,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
        )
        return response
