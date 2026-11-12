"""First-run onboarding: give a signed-in user an organization and an owner role.

Better Auth creates the user row; it does not create a tenant. Until a user has
a membership, every protected route returns "no membership". This bootstraps one
organization, one membership, and an owner role binding for a user who has none.
It authenticates by the Better Auth session token, not by an existing permission,
because a brand-new user has none yet.
"""

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mandate_core.errors import EngineError
from mandate_core.persistence.scope import use_tenant_scope

_SESSION = text(
    """
    select "userId" as user_id
    from auth.session
    where token = :token and "expiresAt" > now()
    """
)

_EXISTING = text(
    """
    select organization_id from identity.memberships
    where user_id = :user_id
    order by created_at
    limit 1
    """
)

_INSERT_ORG = text("insert into identity.organizations (id, name) values (:id, :name)")
_INSERT_MEMBERSHIP = text(
    "insert into identity.memberships (id, organization_id, user_id) values (:id, :organization_id, :user_id)"
)
_INSERT_ROLE = text("insert into identity.role_bindings (membership_id, role) values (:membership_id, :role)")


def bootstrap_membership(connection: Connection, token: str, organization_name: str, request_id: str) -> dict:
    if not token:
        raise EngineError("unauthenticated", "A session token is required.", 401)
    name = (organization_name or "").strip() or "My workspace"

    row = connection.execute(_SESSION, {"token": token}).mappings().first()
    if row is None:
        raise EngineError("unauthenticated", "That session is missing or expired.", 401)
    user_id = UUID(str(row["user_id"]))

    existing = connection.execute(_EXISTING, {"user_id": user_id}).scalar()
    if existing is not None:
        return {"organization_id": str(existing), "created": False}

    organization_id = uuid4()
    membership_id = uuid4()
    use_tenant_scope(connection, organization_id)
    connection.execute(_INSERT_ORG, {"id": organization_id, "name": name})
    connection.execute(_INSERT_MEMBERSHIP, {"id": membership_id, "organization_id": organization_id, "user_id": user_id})
    connection.execute(_INSERT_ROLE, {"membership_id": membership_id, "role": "owner"})
    return {"organization_id": str(organization_id), "membership_id": str(membership_id), "created": True}
