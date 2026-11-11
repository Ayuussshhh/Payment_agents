from fastapi.testclient import TestClient

from mandate_api.app import create_app


class RedisUp:
    def ping(self):
        return True


class RedisDown:
    def ping(self):
        raise ConnectionError("redis down")


def test_health_reports_redis_up():
    client = TestClient(create_app(database_url="", redis_client=RedisUp()))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "database": False, "redis": True}


def test_health_stays_up_when_redis_is_down():
    client = TestClient(create_app(database_url="", redis_client=RedisDown()))
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["redis"] is False


def test_contract_names_the_engine():
    client = TestClient(create_app(database_url="", redis_client=RedisDown()))
    response = client.get("/v1")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Mandate"
    assert body["version"] == "v1"
    assert body["engine_version"] == "0.4.0"
    assert response.headers["x-request-id"].startswith("req_")
    paths = [item["path"] for item in body["resources"]]
    assert "/v1/context" in paths
    models = client.get("/v1/models")
    assert models.status_code == 200
    catalog = models.json()["providers"]
    assert {item["name"] for item in catalog} == {"static", "openai"}
    assert "api_key" not in models.text
