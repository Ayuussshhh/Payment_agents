"""The outbox worker. It publishes committed events, then marks the row delivered.

The event and its audit row are written inside the business transaction; this
worker runs after commit. For now "publish" is a no-op sink — the spine exists so
a real subscriber (a customer webhook, a bus) can be added without touching the
code that writes events. The worker is the only updater of published_at.
"""

from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

_PENDING = text(
    """
    select id, organization_id, name, aggregate_type, aggregate_id, payload, occurred_at
    from events.outbox
    where published_at is null
    order by occurred_at, id
    limit :batch
    for update skip locked
    """
)

_MARK = text(
    """
    update events.outbox set published_at = now()
    where id = any(:ids)
    """
)


def publish_pending(engine: Engine, batch: int = 100, sink: Callable[[dict], None] | None = None) -> int:
    """Publish one batch of unpublished events. Returns how many were delivered."""

    with engine.begin() as connection:
        connection.execute(text("set local app.worker = 'on'"))
        rows = connection.execute(_PENDING, {"batch": batch}).mappings().all()
        if not rows:
            return 0
        for row in rows:
            if sink is not None:
                sink(dict(row))
        connection.execute(_MARK, {"ids": [row["id"] for row in rows]})
        return len(rows)


def run_forever(interval_seconds: float = 1.0) -> None:  # pragma: no cover - a process loop
    """Poll the outbox on an interval. Used by `python -m mandate_core.events.worker`."""
    import time

    from sqlalchemy import create_engine

    from mandate_core.settings import database_url

    url = database_url()
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    engine = create_engine(url, pool_pre_ping=True)
    print("mandate: outbox worker started")
    while True:
        try:
            delivered = publish_pending(engine)
            if delivered:
                print(f"mandate: published {delivered} event(s)")
        except Exception as exc:  # keep the loop alive across transient DB errors
            print(f"mandate: worker retry after error: {exc}")
            time.sleep(min(interval_seconds * 5, 10.0))
        time.sleep(interval_seconds)


if __name__ == "__main__":  # pragma: no cover
    run_forever()
