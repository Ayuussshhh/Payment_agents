"""Trusted values that cross a subsystem boundary."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from mandate_core.errors import EngineError


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionLimits(ContractModel):
    max_steps: int = Field(ge=1, le=64, default=12)
    max_model_calls: int = Field(ge=1, le=64, default=12)
    max_input_tokens: int = Field(ge=1, default=100_000)
    max_output_tokens: int = Field(ge=1, default=8_000)
    deadline_ms: int = Field(ge=1_000, le=120_000, default=60_000)


class ExecutionContext(ContractModel):
    """Built from the authenticated principal and the database.

    Frozen so a caller cannot swap the organization after construction.
    Model output is not a valid source for this object.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: UUID
    user_id: UUID | None
    agent_id: UUID | None = None
    agent_version_id: UUID | None = None
    run_id: UUID | None = None
    policy_version_id: UUID | None = None
    permissions: tuple[str, ...] = ()
    skill_allowlist: tuple[str, ...] = ()
    request_id: str
    idempotency_key: str | None = None
    limits: ExecutionLimits = Field(default_factory=ExecutionLimits)


_MODEL_CONTROLLED = frozenset(
    {
        "organization_id",
        "user_id",
        "permissions",
        "policy_version_id",
        "agent_version_id",
        "skill_allowlist",
    }
)


def refuse_model_context(payload: dict) -> None:
    """Model output, tool arguments, and catalog text cannot become a context."""

    if not isinstance(payload, dict):
        raise EngineError("context_mutation", "Model output cannot set execution context.", 409)
    found = _MODEL_CONTROLLED.intersection(payload)
    if found:
        raise EngineError("context_mutation", "Model output cannot set execution context.", 409)
