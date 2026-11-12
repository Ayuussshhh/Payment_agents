"""Read the audit timeline for one aggregate, and check it is complete and ordered.

This is not cryptographic immutability — the product must not claim that. The
history is an append-only table protected by database grants; a hash chain is a
later addition. verify_history confirms the rows for an aggregate are present and
time-ordered.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mandate_core.contracts import ExecutionContext
from mandate_core.identity import authorize_action
from mandate_core.persistence.scope import use_tenant_scope

_TIMELINE = text(
    """
    select id, name, aggregate_type, aggregate_id, actor_type, actor_id, request_id,
           reason_code, payload, occurred_at
    from events.audit_events
    where organization_id = :organization_id
      and aggregate_type = :aggregate_type
      and aggregate_id = :aggregate_id
    order by occurred_at, id
    """
)


def _row(row) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "aggregate_type": row["aggregate_type"],
        "aggregate_id": str(row["aggregate_id"]),
        "actor_type": row["actor_type"],
        "actor_id": row["actor_id"],
        "request_id": row["request_id"],
        "reason_code": row["reason_code"],
        "payload": row["payload"],
        "occurred_at": row["occurred_at"].isoformat() if row["occurred_at"] else None,
    }


def get_timeline(connection: Connection, context: ExecutionContext, aggregate_type: str, aggregate_id: UUID) -> list[dict]:
    authorize_action(context, "read", "AuditEvent")
    use_tenant_scope(connection, context.organization_id)
    rows = connection.execute(
        _TIMELINE,
        {"organization_id": context.organization_id, "aggregate_type": aggregate_type, "aggregate_id": aggregate_id},
    ).mappings().all()
    return [_row(row) for row in rows]


def verify_history(connection: Connection, context: ExecutionContext, aggregate_type: str, aggregate_id: UUID) -> dict:
    """Confirm the timeline is present and non-decreasing in time. Names every event."""

    events = get_timeline(connection, context, aggregate_type, aggregate_id)
    ordered = all(
        events[index - 1]["occurred_at"] <= events[index]["occurred_at"]
        for index in range(1, len(events))
        if events[index - 1]["occurred_at"] and events[index]["occurred_at"]
    )
    return {
        "aggregate_type": aggregate_type,
        "aggregate_id": str(aggregate_id),
        "count": len(events),
        "ordered": ordered,
        "complete": len(events) > 0,
        "names": [event["name"] for event in events],
        "first_at": events[0]["occurred_at"] if events else None,
        "last_at": events[-1]["occurred_at"] if events else None,
    }
