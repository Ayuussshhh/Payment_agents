"""Record token counts. A failed call does not write a row."""

from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mandate_core.contracts import ExecutionContext
from mandate_core.identity import authorize_action
from mandate_core.models.types import TokenUsage
from mandate_core.persistence.scope import use_tenant_scope


_USAGE_TOTALS = text(
    """
    select provider, model,
           count(*) as calls,
           coalesce(sum(input_tokens), 0) as input_tokens,
           coalesce(sum(output_tokens), 0) as output_tokens
    from usage.token_usage
    where organization_id = :organization_id
    group by provider, model
    order by provider, model
    """
)


def read_usage(connection: Connection, context: ExecutionContext) -> dict:
    """Token counts for the organization, grouped by provider and model."""
    authorize_action(context, "read", "ModelConfig")
    use_tenant_scope(connection, context.organization_id)
    rows = connection.execute(_USAGE_TOTALS, {"organization_id": context.organization_id}).mappings().all()
    by_model = [
        {
            "provider": row["provider"],
            "model": row["model"],
            "calls": int(row["calls"]),
            "input_tokens": int(row["input_tokens"]),
            "output_tokens": int(row["output_tokens"]),
        }
        for row in rows
    ]
    return {
        "by_model": by_model,
        "input_tokens": sum(item["input_tokens"] for item in by_model),
        "output_tokens": sum(item["output_tokens"] for item in by_model),
        "calls": sum(item["calls"] for item in by_model),
    }


class UsageWriter(Protocol):
    def record(self, usage: TokenUsage) -> None: ...


class MemoryUsage:
    def __init__(self):
        self.rows: list[TokenUsage] = []

    def record(self, usage: TokenUsage) -> None:
        self.rows.append(usage)


class SqlUsage:
    def __init__(self, connection: Connection):
        self.connection = connection

    def record(self, usage: TokenUsage) -> None:
        use_tenant_scope(self.connection, usage.organization_id)
        self.connection.execute(
            text(
                """
                insert into usage.token_usage (
                  organization_id, run_id, provider, model, input_tokens, output_tokens
                )
                values (:organization_id, :run_id, :provider, :model, :input_tokens, :output_tokens)
                """
            ),
            usage.model_dump(),
        )
