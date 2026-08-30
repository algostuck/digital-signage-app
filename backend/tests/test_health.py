async def test_health_liveness(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == {"status": "ok"}
    assert body["errors"] == []
    assert body["meta"]["request_id"]
    assert resp.headers["X-Request-ID"] == body["meta"]["request_id"]


async def test_health_readiness_hits_database(client):
    resp = await client.get("/api/v1/health/ready")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"status": "ready", "database": "ok"}


async def test_request_id_is_propagated(client):
    resp = await client.get("/api/v1/health", headers={"X-Request-ID": "test-rid-123"})
    assert resp.headers["X-Request-ID"] == "test-rid-123"
    assert resp.json()["meta"]["request_id"] == "test-rid-123"


async def test_unknown_route_uses_error_envelope(client):
    resp = await client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["data"] is None
    assert body["errors"][0]["code"] == "NOT_FOUND"
