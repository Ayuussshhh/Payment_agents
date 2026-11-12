"""Provider webhooks. An unverified body never changes a row.

Verification is the adapter's job. This module deduplicates on the provider's
event id and advances a matching transaction out of `unknown` (or confirms a
terminal state). It never creates a second charge.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mandate_core.commerce.provider import PaymentProvider, ProviderEvent
from mandate_core.errors import EngineError

_SEEN = text(
    """
    select id from integrations.webhook_deliveries
    where provider = :provider and event_id = :event_id
    """
)

_RECORD = text(
    """
    insert into integrations.webhook_deliveries (
      id, provider, event_id, event_type, verified, received_at, raw
    )
    values (:id, :provider, :event_id, :event_type, :verified, :received_at, cast(:raw as jsonb))
    on conflict (provider, event_id) do nothing
    """
)

_TXN_BY_ORDER = text(
    """
    select id, organization_id, status from commerce.transactions
    where provider = :provider and provider_order_id = :provider_order_id
    """
)

_ADVANCE = text(
    """
    update commerce.transactions
    set status = :status, reason_code = :reason_code, updated_at = now()
    where id = :transaction_id
    """
)

# A verified event type maps to the state it confirms. unknown resolves to these.
_RESOLVES = {
    "PAYMENT.AUTHORIZATION.CREATED": "authorized",
    "PAYMENT.CAPTURE.COMPLETED": "captured",
    "PAYMENT.AUTHORIZATION.VOIDED": "voided",
    "PAYMENT.CAPTURE.DENIED": "failed",
}


async def handle_webhook(connection: Connection, provider: PaymentProvider, headers: dict, body: bytes) -> dict:
    event: ProviderEvent = await provider.verify_webhook(headers, body)
    if not event.verified:
        raise EngineError("webhook_unverified", "The webhook signature did not verify.", 400)

    seen = connection.execute(_SEEN, {"provider": provider.name, "event_id": event.event_id}).first()
    connection.execute(
        _RECORD,
        {
            "id": uuid4(),
            "provider": provider.name,
            "event_id": event.event_id,
            "event_type": event.event_type,
            "verified": True,
            "received_at": datetime.now(timezone.utc),
            "raw": json.dumps(event.raw),
        },
    )
    if seen is not None:
        return {"status": "duplicate", "event_id": event.event_id}

    target = _RESOLVES.get(event.event_type)
    if target is None or not event.provider_order_id:
        return {"status": "ignored", "event_id": event.event_id}

    row = connection.execute(
        _TXN_BY_ORDER, {"provider": provider.name, "provider_order_id": event.provider_order_id}
    ).mappings().first()
    if row is None:
        return {"status": "no_match", "event_id": event.event_id}

    # Only move a holding transaction forward. A settled row is left as it is.
    if row["status"] == "unknown":
        connection.execute(_ADVANCE, {"status": target, "reason_code": "resolved_by_webhook", "transaction_id": row["id"]})
        return {"status": "resolved", "transaction_id": str(row["id"]), "to": target}
    return {"status": "noted", "transaction_id": str(row["id"]), "current": row["status"]}
