"""Domain objects shared by the engine subsystems."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field

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
    skill_names: tuple[str, ...] = ()
    voice_id: str | None = None
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


class PolicyVersion(ContractModel):
    """One immutable policy document. Status moves draft, then active, then retired."""

    id: UUID
    organization_id: UUID
    policy_id: UUID
    name: str
    version: int = Field(ge=1)
    status: Literal["draft", "active", "retired"]
    currency: str = Field(min_length=3, max_length=3)
    maximum_total_minor: int = Field(gt=0)
    constraints: dict
    original_instruction: str
    ambiguities: tuple[str, ...] = ()
    preferences: tuple[str, ...] = ()
    expires_at: datetime
    created_at: datetime
    activated_at: datetime | None = None


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


class ApprovalSnapshot(ContractModel):
    """The exact cart a person approved. The database row is the authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: UUID
    approver_user_id: UUID
    agent_version_id: UUID | None = None
    policy_version_id: UUID
    policy_version: int
    proposal_id: UUID
    cart_hash: str
    hash_version: int
    amount_minor: int
    currency: str
    merchant_id: str
    expires_at: datetime


class Approval(ContractModel):
    id: UUID
    organization_id: UUID
    proposal_id: UUID
    policy_version_id: UUID
    policy_version: int
    agent_version_id: UUID | None = None
    approver_user_id: UUID | None = None
    cart_hash: str
    hash_version: int
    amount_minor: int
    currency: str
    merchant_id: str
    status: Literal["pending", "valid", "rejected", "expired", "revoked", "consumed"]
    expires_at: datetime
    created_at: datetime
    signature: str | None = None


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


TransactionStatus = Literal[
    "prepared",
    "reserved",
    "authorized",
    "captured",
    "voided",
    "refunded",
    "failed",
    "unknown",
]


class Transaction(ContractModel):
    """One payment, provider-independent. The row is the authority; a provider
    willing to charge a nearby amount is irrelevant."""

    id: UUID
    organization_id: UUID
    proposal_id: UUID
    approval_id: UUID
    policy_version_id: UUID
    cart_hash: str
    amount_minor: int
    currency: str
    status: TransactionStatus
    provider: str
    provider_order_id: str | None = None
    provider_authorization_id: str | None = None
    provider_capture_id: str | None = None
    provider_approval_url: str | None = None
    reason_code: str = ""
    idempotency_key: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
