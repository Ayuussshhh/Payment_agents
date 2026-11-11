"""Record token counts. A failed call does not write a row."""

from typing import Protocol

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mandate_core.models.types import TokenUsage
from mandate_core.persistence.scope import use_tenant_scope


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
