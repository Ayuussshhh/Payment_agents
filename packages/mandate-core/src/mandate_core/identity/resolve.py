"""Resolve a Better Auth session into an execution context.

Column names match the auth schema committed in the Alembic revision for
Better Auth 1.7.20. User ids are UUIDs because the web app sets generateId
to uuid.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mandate_core.contracts import ExecutionContext
from mandate_core.errors import EngineError
from mandate_core.identity.catalog import expand_roles

_SESSION = text(
    """
    select "userId" as user_id
    from auth.session
    where token = :token
      and "expiresAt" > now()
    """
)

_MEMBERSHIPS = text(
    """
    select m.organization_id, m.id as membership_id
    from identity.memberships m
    where m.user_id = :user_id
    order by m.created_at
    """
)

_ROLES = text(
    """
    select role
    from identity.role_bindings
    where membership_id = :membership_id
    order by role
    """
)


def _as_uuid(value) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def resolve_execution_context(
    connection: Connection,
    token: str,
    *,
    organization_id: UUID | None,
    request_id: str,
) -> ExecutionContext:
    if not token:
        raise EngineError("unauthenticated", "A session token is required.", 401)
    row = connection.execute(_SESSION, {"token": token}).mappings().first()
    if row is None:
        raise EngineError("unauthenticated", "That session is missing or expired.", 401)
    user_id = _as_uuid(row["user_id"])

    memberships = [
        {**item, "organization_id": _as_uuid(item["organization_id"])}
        for item in connection.execute(_MEMBERSHIPS, {"user_id": user_id}).mappings()
    ]
    if organization_id is None:
        if len(memberships) == 0:
            raise EngineError("not_found", "That user has no membership in an organization.", 404)
        if len(memberships) != 1:
            raise EngineError("organization_required", "Choose an organization.", 400)
        chosen = memberships[0]
    else:
        chosen = next((item for item in memberships if item["organization_id"] == organization_id), None)
        if chosen is None:
            raise EngineError("not_found", "That user has no membership in an organization.", 404)

    roles = [
        item["role"]
        for item in connection.execute(_ROLES, {"membership_id": chosen["membership_id"]}).mappings()
    ]
    return ExecutionContext(
        organization_id=chosen["organization_id"],
        user_id=user_id,
        permissions=expand_roles(roles) if roles else (),
        request_id=request_id,
    )
