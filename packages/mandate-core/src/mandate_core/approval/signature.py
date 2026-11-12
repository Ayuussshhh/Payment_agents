"""Server-side signature over the canonical approval snapshot. The row outranks the token."""

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

from mandate_core.errors import EngineError
from mandate_core.settings import load_env


def signing_key(explicit: bytes | None = None) -> bytes:
    if explicit:
        return explicit
    load_env()
    value = os.environ.get("APPROVAL_SIGNING_KEY", "").strip()
    if not value:
        raise EngineError("configuration", "APPROVAL_SIGNING_KEY is not set.", 503)
    return value.encode("utf-8")


def stamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc).replace(microsecond=0)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def snapshot_bytes(fields: dict) -> bytes:
    body = {
        "agent_version_id": None if fields.get("agent_version_id") is None else str(fields["agent_version_id"]),
        "amount_minor": fields["amount_minor"],
        "approver_user_id": str(fields["approver_user_id"]),
        "cart_hash": fields["cart_hash"],
        "currency": fields["currency"],
        "expires_at": fields["expires_at"] if isinstance(fields["expires_at"], str) else stamp(fields["expires_at"]),
        "hash_version": fields["hash_version"],
        "merchant_id": fields["merchant_id"],
        "organization_id": str(fields["organization_id"]),
        "policy_version": fields["policy_version"],
        "policy_version_id": str(fields["policy_version_id"]),
        "proposal_id": str(fields["proposal_id"]),
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_snapshot(fields: dict, key: bytes | None = None) -> str:
    digest = hmac.new(signing_key(key), snapshot_bytes(fields), hashlib.sha256).hexdigest()
    return digest


def token_matches(fields: dict, token: str, key: bytes | None = None) -> bool:
    if not token:
        return False
    expected = sign_snapshot(fields, key)
    return hmac.compare_digest(expected, token)
