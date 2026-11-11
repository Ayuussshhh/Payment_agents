from uuid import uuid4

from fastapi import Request
from fastapi.testclient import TestClient

from mandate_api.app import create_app
from mandate_core.errors import EngineError


class RedisDown:
    def ping(self):
        raise ConnectionError("redis down")


def test_not_found_carries_the_error_body_and_request_id():
    app = create_app(database_url="", redis_client=RedisDown())

    @app.get("/v1/forced-missing")
    def forced(request: Request):
        raise EngineError("not_found", "That resource does not exist.", 404)

    client = TestClient(app)
    response = client.get("/v1/forced-missing", headers={"X-Request-Id": "req_fixed"})
    assert response.status_code == 404
    assert response.headers["x-request-id"] == "req_fixed"
    body = response.json()["error"]
    assert body["code"] == "not_found"
    assert body["message"] == "That resource does not exist."
    assert body["request_id"] == "req_fixed"
    assert "details" in body


def test_agent_routes_are_on_the_contract():
    client = TestClient(create_app(database_url="", redis_client=RedisDown()))
    paths = [item["path"] for item in client.get("/v1").json()["resources"]]
    assert "/v1/agents" in paths
    assert "/v1/agents/{id}/versions" in paths
    missing = client.get(f"/v1/agents/{uuid4()}")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "unauthenticated"
