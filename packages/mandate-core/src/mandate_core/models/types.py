"""Requests and responses for every model provider."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from mandate_core.contracts.context import ContractModel


class ModelCapabilities(ContractModel):
    tool_calling: bool
    structured_output: bool
    streaming: bool
    context_window: int = Field(ge=1)
    input_types: tuple[str, ...] = ("text",)
    reasoning_modes: tuple[str, ...] = ()


class ModelMessage(ContractModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ToolCall(ContractModel):
    name: str
    arguments: dict = Field(default_factory=dict)


class ModelRequest(ContractModel):
    provider: str
    model: str
    messages: tuple[ModelMessage, ...]
    tools: tuple[dict, ...] = ()
    temperature: float = Field(ge=0, le=2, default=0)
    json_object: bool = False


class ModelResponse(ContractModel):
    provider: str
    model: str
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    input_tokens: int = Field(ge=0, default=0)
    output_tokens: int = Field(ge=0, default=0)


class ModelEvent(ContractModel):
    content: str = ""
    done: bool = False
    input_tokens: int = 0
    output_tokens: int = 0


class TokenUsage(ContractModel):
    organization_id: UUID
    run_id: UUID | None = None
    provider: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class TransportResult(ContractModel):
    status: int
    body: dict = Field(default_factory=dict)
    lines: tuple[str, ...] = ()
