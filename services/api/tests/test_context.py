import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from mandate_api.app import create_app

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is not set")


def _engine():
    return create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


@pytest.fixture(scope="module")
def migrated():
    from alembic import command
    from alembic.config import Config

    config = Config("packages/mandate-core/alembic.ini")
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    return _engine()


def _seed(connection, *, with_membership):
    user_id = uuid4()
    token = f"session-{uuid4().hex}"
    connection.execute(
        text(
            """
            insert into auth."user" (id, name, email, "emailVerified")
            values (:id, 'Owner', :email, true)
            """
        ),
        {"id": user_id, "email": f"{user_id}@example.com"},
    )
    connection.execute(
        text(
            """
            insert into auth.session (id, "expiresAt", token, "userId")
            values (:id, :expires, :token, :user_id)
            """
        ),
        {
            "id": uuid4(),
            "expires": datetime.now(timezone.utc) + timedelta(hours=1),
            "token": token,
            "user_id": user_id,
        },
    )
    organization_id = None
    if with_membership:
        organization_id = uuid4()
        membership_id = uuid4()
        connection.execute(
            text("insert into identity.organizations (id, name) values (:id, 'Acme')"),
            {"id": organization_id},
        )
        connection.execute(
            text(
                """
                insert into identity.memberships (id, organization_id, user_id)
                values (:id, :organization_id, :user_id)
                """
            ),
            {"id": membership_id, "organization_id": organization_id, "user_id": user_id},
        )
        connection.execute(
            text("insert into identity.role_bindings (membership_id, role) values (:id, 'owner')"),
            {"id": membership_id},
        )
    connection.commit()
    return token, organization_id


def test_valid_session_resolves_an_owner_context(migrated):
    with migrated.connect() as connection:
        token, organization_id = _seed(connection, with_membership=True)
    client = TestClient(create_app(database_url="", redis_client=None, engine=migrated))
    response = client.get("/v1/context", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()["context"]
    assert body["organization_id"] == str(organization_id)
    assert "approve:Approval" in body["permissions"]
    assert body["user_id"]


def test_missing_session_is_unauthenticated(migrated):
    client = TestClient(create_app(database_url="", redis_client=None, engine=migrated))
    response = client.get("/v1/context", headers={"Authorization": "Bearer missing"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_user_without_a_membership_is_not_found(migrated):
    with migrated.connect() as connection:
        token, _organization = _seed(connection, with_membership=False)
    client = TestClient(create_app(database_url="", redis_client=None, engine=migrated))
    response = client.get("/v1/context", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
