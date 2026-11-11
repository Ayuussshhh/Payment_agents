"""Apply the organization setting and the application role for one transaction."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection


def use_tenant_scope(connection: Connection, organization_id: UUID) -> None:
    connection.execute(text("set local role mandate_app"))
    connection.execute(
        text("select set_config('app.organization_id', :organization_id, true)"),
        {"organization_id": str(organization_id)},
    )
