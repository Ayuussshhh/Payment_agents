import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from mandate_core.contracts import EventEnvelope, ExecutionContext
from mandate_core.errors import EngineError
from mandate_core.events import append_event
from mandate_core.persistence.agents import AgentRepository

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is not set")


def _engine():
    return create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


@pytest.fixture(scope="module")
def database():
    from alembic import command
    from alembic.config import Config

    config = Config("packages/mandate-core/alembic.ini")
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    return _engine()


def _organization(connection):
    organization_id = uuid4()
    connection.execute(
        text("select set_config('app.organization_id', :organization_id, true)"),
        {"organization_id": str(organization_id)},
    )
    connection.execute(
        text("insert into identity.organizations (id, name) values (:id, 'Acme')"),
        {"id": organization_id},
    )
    return organization_id


def _context(organization_id):
    return ExecutionContext(organization_id=organization_id, user_id=uuid4(), request_id="req_test")


def test_publish_is_immutable_and_versions_increase(database):
    repository = AgentRepository()
    with database.begin() as connection:
        organization_id = _organization(connection)
        context = _context(organization_id)
        agent = repository.create_agent(connection, context, "Buyer", "", "buyer")
        first = repository.publish_version(
            connection, context, agent.id, provider="openai", model="gpt-4o-mini", temperature=0, system_prompt="first"
        )
        second = repository.publish_version(
            connection, context, agent.id, provider="openai", model="gpt-4o-mini", temperature=0, system_prompt="second"
        )
        version_id = first.id
    assert first.version == 1
    assert second.version == 2
    assert first.system_prompt == "first"

    with database.connect() as connection:
        with pytest.raises(DBAPIError) as caught:
            connection.execute(
                text("update agents.agent_versions set system_prompt = 'changed' where id = :id"),
                {"id": version_id},
            )
        assert "immutable" in str(caught.value)
        connection.rollback()
        stored = connection.execute(
            text("select system_prompt from agents.agent_versions where id = :id"),
            {"id": version_id},
        ).scalar_one()
    assert stored == "first"

    with database.begin() as connection:
        with pytest.raises(EngineError) as caught_error:
            repository.replace_prompt(connection, _context(organization_id), version_id, "changed")
    assert caught_error.value.code == "version_immutable"


def test_events_commit_and_roll_back_together(database):
    with database.begin() as connection:
        organization_id = _organization(connection)
    context = _context(organization_id)
    event = EventEnvelope(
        id=uuid4(),
        organization_id=organization_id,
        name="agent.created",
        aggregate_type="agent",
        aggregate_id=uuid4(),
        actor_type="user",
        actor_id=str(context.user_id),
        request_id=context.request_id,
        payload={"name": "Buyer"},
        occurred_at=datetime.now(timezone.utc),
    )
    with database.connect() as connection:
        append_event(connection, context, event)
        connection.rollback()
        outbox = connection.execute(text("select count(*) from events.outbox where id = :id"), {"id": event.id}).scalar_one()
        audit = connection.execute(text("select count(*) from events.audit_events where id = :id"), {"id": event.id}).scalar_one()
    assert outbox == 0
    assert audit == 0

    with database.begin() as connection:
        append_event(connection, context, event)
    with database.connect() as connection:
        outbox = connection.execute(text("select count(*) from events.outbox where id = :id"), {"id": event.id}).scalar_one()
        audit = connection.execute(text("select count(*) from events.audit_events where id = :id"), {"id": event.id}).scalar_one()
    assert outbox == 1
    assert audit == 1


def test_another_organization_sees_no_rows(database):
    with database.begin() as connection:
        organization_id = _organization(connection)
    other = uuid4()
    with database.connect() as connection:
        connection.execute(text("set local role mandate_app"))
        hidden = connection.execute(text("select id from identity.organizations")).all()
        connection.execute(
            text("select set_config('app.organization_id', :organization_id, true)"),
            {"organization_id": str(other)},
        )
        wrong_org = connection.execute(
            text("select id from identity.organizations where id = :id"),
            {"id": organization_id},
        ).all()
        connection.execute(
            text("select set_config('app.organization_id', :organization_id, true)"),
            {"organization_id": str(organization_id)},
        )
        visible = connection.execute(
            text("select id from identity.organizations where id = :id"),
            {"id": organization_id},
        ).all()
    assert hidden == []
    assert wrong_org == []
    assert len(visible) == 1
