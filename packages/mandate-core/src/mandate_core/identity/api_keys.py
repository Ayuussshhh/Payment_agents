"""Organization API keys for the developer platform.

The secret is shown once at creation and stored only as a SHA-256 hash. A key
authenticates a programmatic principal scoped to one organization. It cannot
approve a payment — approvals require a human user — so a leaked key cannot move
money on its own. Revocation is immediate: a revoked row never resolves.
"""

import hashlib
import secrets
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mandate_core.contracts import ExecutionContext
from mandate_core.errors import EngineError
from mandate_core.identity import authorize_action

_PREFIX = "mk"

_INSERT = text(
    """
    insert into identity.api_keys (id, organization_id, name, prefix, secret_hash, created_by)
    values (:id, :organization_id, :name, :prefix, :secret_hash, :created_by)
    """
)

_LIST = text(
    """
    select id, name, prefix, created_by, revoked_at, created_at
    from identity.api_keys
    where organization_id = :organization_id
    order by created_at desc
    """
)

_REVOKE = text(
    """
    update identity.api_keys set revoked_at = now()
    where organization_id = :organization_id and id = :id and revoked_at is null
    """
)

_BY_PREFIX = text(
    """
    select id, organization_id, secret_hash, revoked_at
    from identity.api_keys
    where prefix = :prefix
    """
)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _mint() -> tuple[str, str]:
    """Return (prefix, full_secret). The prefix identifies the row; the secret proves it."""
    prefix = secrets.token_hex(4)
    body = secrets.token_hex(24)
    return prefix, f"{_PREFIX}_{prefix}_{body}"


def _meta(row) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "prefix": row["prefix"],
        "created_by": row["created_by"],
        "revoked_at": row["revoked_at"].isoformat() if row["revoked_at"] else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def create_key(connection: Connection, context: ExecutionContext, name: str) -> dict:
    authorize_action(context, "create", "ApiKey")
    if not name.strip():
        raise EngineError("validation", "A key name is required.", 400)
    from mandate_core.persistence.scope import use_tenant_scope

    use_tenant_scope(connection, context.organization_id)
    prefix, secret = _mint()
    key_id = uuid4()
    connection.execute(
        _INSERT,
        {
            "id": key_id,
            "organization_id": context.organization_id,
            "name": name.strip(),
            "prefix": prefix,
            "secret_hash": hash_secret(secret),
            "created_by": str(context.user_id),
        },
    )
    return {"id": str(key_id), "name": name.strip(), "prefix": prefix, "secret": secret}


def list_keys(connection: Connection, context: ExecutionContext) -> list[dict]:
    authorize_action(context, "read", "ApiKey")
    from mandate_core.persistence.scope import use_tenant_scope

    use_tenant_scope(connection, context.organization_id)
    rows = connection.execute(_LIST, {"organization_id": context.organization_id}).mappings().all()
    return [_meta(row) for row in rows]


def revoke_key(connection: Connection, context: ExecutionContext, key_id: UUID) -> dict:
    authorize_action(context, "revoke", "ApiKey")
    from mandate_core.persistence.scope import use_tenant_scope

    use_tenant_scope(connection, context.organization_id)
    updated = connection.execute(_REVOKE, {"organization_id": context.organization_id, "id": key_id}).rowcount
    if not updated:
        raise EngineError("not_found", "That key does not exist or is already revoked.", 404)
    return {"id": str(key_id), "revoked": True}


def resolve_key(connection: Connection, secret: str) -> UUID:
    """Return the organization id a key belongs to, or raise unauthenticated.

    Runs outside tenant scope because the caller is not yet known. It reads only
    by prefix and compares the hash in constant time.
    """
    parts = secret.split("_")
    if len(parts) != 3 or parts[0] != _PREFIX:
        raise EngineError("unauthenticated", "That API key is malformed.", 401)
    row = connection.execute(_BY_PREFIX, {"prefix": parts[1]}).mappings().first()
    if row is None or row["revoked_at"] is not None:
        raise EngineError("unauthenticated", "That API key is unknown or revoked.", 401)
    if not secrets.compare_digest(row["secret_hash"], hash_secret(secret)):
        raise EngineError("unauthenticated", "That API key did not verify.", 401)
    return row["organization_id"]
