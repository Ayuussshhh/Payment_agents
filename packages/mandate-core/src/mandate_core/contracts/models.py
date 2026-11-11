"""Domain objects shared by the engine subsystems."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from mandate_core.contracts.context import ContractModel


class AgentDefinition(ContractModel):
    id: UUID
    organization_id: UUID
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    graph_kind: Literal["compiler", "buyer"]
    created_at: datetime


class ModelRef(ContractModel):
    provider: str
    model: str
    temperature: float = Field(ge=0, le=2, default=0)


class FallbackRef(ContractModel):
    model: ModelRef
    required_capabilities: tuple[str, ...] = ()


class AgentVersion(ContractModel):
    id: UUID
    agent_id: UUID
    organization_id: UUID
    version: int = Field(ge=1)
    model: ModelRef
    fallbacks: tuple[FallbackRef, ...] = ()
    system_prompt: str
    skill_ids: tuple[UUID, ...] = ()
    published_at: datetime
    published_by: UUID


class AgentRun(ContractModel):
    id: UUID
    organization_id: UUID
    agent_version_id: UUID
    policy_version_id: UUID | None = None
    status: Literal["queued", "running", "succeeded", "failed", "cancelled", "limited"]
    input: dict
    output: dict = Field(default_factory=dict)
    stop_reason: str = ""
    created_at: datetime
    finished_at: datetime | None = None
    cancel_requested: bool = False


class RequiredSpecs(ContractModel):
    ram_gb_min: int = Field(ge=1)
    storage_gb_min: int = Field(ge=1)
    storage_type: Literal["ssd"]


class PolicyDraft(ContractModel):
    """Compiler output. Status is not a field, so a model cannot activate a policy."""

    currency: str = Field(min_length=3, max_length=3)
    maximum_total_minor: int = Field(gt=0)
    amount_includes: tuple[str, ...]
    allowed_brands: tuple[str, ...]
    required_specs: RequiredSpecs
    forbidden_addon_types: tuple[str, ...]
    max_executions: int = Field(ge=1)
    approval_required: bool
    preferences: tuple[str, ...]
    ambiguities: tuple[str, ...]
    original_instruction: str


class Seller(ContractModel):
    id: str


class CartLine(ContractModel):
    sku: str
    brand: str
    quantity: int = Field(ge=1)
    unit_amount_minor: int = Field(ge=0)
    addon_type: str | None = None
    ram_gb: int | None = None
    storage_gb: int | None = None
    storage_type: str | None = None


class Proposal(ContractModel):
    currency: str = Field(min_length=3, max_length=3)
    mandate_id: UUID
    mandate_version: int
    seller: Seller
    lines: tuple[CartLine, ...]
    total_minor: int = Field(ge=0)


class PolicyDecision(ContractModel):
    decision: Literal["allow", "deny", "needs_approval"]
    reason_codes: tuple[str, ...]
    policy_version_id: UUID
    policy_version: int
    cart_hash: str | None = None
    evaluated_amount_minor: int | None = None
    maximum_amount_minor: int | None = None
    currency: str | None = None
    explanations: tuple[dict, ...] = ()


class EventEnvelope(ContractModel):
    id: UUID
    organization_id: UUID
    name: str
    aggregate_type: str
    aggregate_id: UUID
    actor_type: Literal["user", "agent", "system", "provider"]
    actor_id: str
    request_id: str
    payload: dict
    occurred_at: datetime
