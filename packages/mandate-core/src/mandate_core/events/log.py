"""Write an event and its audit row in the caller's transaction."""

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mandate_core.contracts import EventEnvelope, ExecutionContext
from mandate_core.errors import EngineError
from mandate_core.persistence.scope import use_tenant_scope

_OUTBOX = text(
    """
    insert into events.outbox (
      id, organization_id, name, aggregate_type, aggregate_id, payload, occurred_at
    )
    values (
      :id, :organization_id, :name, :aggregate_type, :aggregate_id, cast(:payload as jsonb), :occurred_at
    )
    """
)

_AUDIT = text(
    """
    insert into events.audit_events (
      id, organization_id, name, aggregate_type, aggregate_id, actor_type, actor_id, request_id, payload, occurred_at
    )
    values (
      :id, :organization_id, :name, :aggregate_type, :aggregate_id, :actor_type, :actor_id, :request_id,
      cast(:payload as jsonb), :occurred_at
    )
    """
)


def append_event(connection: Connection, context: ExecutionContext, event: EventEnvelope) -> None:
    if event.organization_id != context.organization_id:
        raise EngineError("not_found", "That event is outside this organization.", 404)
    use_tenant_scope(connection, context.organization_id)
    payload = json_payload(event.payload)
    connection.execute(
        _OUTBOX,
        {
            "id": event.id,
            "organization_id": event.organization_id,
            "name": event.name,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "payload": payload,
            "occurred_at": event.occurred_at,
        },
    )
    connection.execute(
        _AUDIT,
        {
            "id": event.id,
            "organization_id": event.organization_id,
            "name": event.name,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "actor_type": event.actor_type,
            "actor_id": event.actor_id,
            "request_id": event.request_id,
            "payload": payload,
            "occurred_at": event.occurred_at,
        },
    )


def json_payload(payload: dict) -> str:
    import json

    return json.dumps(payload)
