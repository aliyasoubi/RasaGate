"""Intent CRUD tests — each test runs against a fresh in-memory DB."""


def _create_greet(client):
    return client.post("/api/v1/intents/", json={
        "name": "greet",
        "examples": ["hi", "hello"],
        "responses": ["Hi there!"],
    })


def test_create_intent(client):
    r = _create_greet(client)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "success"
    assert body["data"]["name"] == "greet"
    assert len(body["data"]["examples"]) == 2
    assert len(body["data"]["responses"]) == 1


def test_invalid_intent_name_rejected(client):
    r = client.post("/api/v1/intents/", json={"name": "Bad Name"})
    assert r.status_code == 400  # custom validation handler maps 422 -> 400
    assert r.json()["error_code"] == "VALIDATION_ERROR"


def test_duplicate_intent_conflict(client):
    assert _create_greet(client).status_code == 201
    r = _create_greet(client)
    assert r.status_code == 409
    assert r.json()["error_code"] == "INTENT_ALREADY_EXISTS"


def test_get_missing_intent_404(client):
    r = client.get("/api/v1/intents/nope")
    assert r.status_code == 404
    assert r.json()["error_code"] == "INTENT_NOT_FOUND"


def test_missing_example_returns_404_not_500(client):
    """Regression: ResourceNotFoundError used to bypass handlers -> 500."""
    _create_greet(client)
    r = client.put(
        "/api/v1/intents/greet/examples/9999", json={"text": "hey"}
    )
    assert r.status_code == 404
    assert r.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_delete_cascades(client):
    _create_greet(client)
    r = client.delete("/api/v1/intents/greet")
    assert r.status_code == 200
    assert client.get("/api/v1/intents/greet").status_code == 404
