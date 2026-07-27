# tests/test_responses.py
"""Response sub-resource tests — add / update / delete response variations."""


def _create_greet(client):
    return client.post("/api/v1/intents/", json={
        "name": "greet",
        "examples": ["hi"],
        "responses": ["Hi there!"],
    })


def test_add_response_variation(client):
    _create_greet(client)
    r = client.post(
        "/api/v1/intents/greet/responses", json={"text": "Hello!"}
    )
    assert r.status_code == 201
    assert r.json()["data"]["text"] == "Hello!"

    # Intent should now report both variations.
    intent = client.get("/api/v1/intents/greet").json()["data"]
    assert {r["text"] for r in intent["responses"]} == {"Hi there!", "Hello!"}


def test_update_response(client):
    _create_greet(client)
    response_id = client.get("/api/v1/intents/greet").json()["data"]["responses"][0]["id"]

    r = client.put(
        f"/api/v1/intents/greet/responses/{response_id}",
        json={"text": "Howdy!"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["text"] == "Howdy!"


def test_delete_response(client):
    _create_greet(client)
    response_id = client.get("/api/v1/intents/greet").json()["data"]["responses"][0]["id"]

    r = client.delete(f"/api/v1/intents/greet/responses/{response_id}")
    assert r.status_code == 200

    intent = client.get("/api/v1/intents/greet").json()["data"]
    assert intent["responses"] == []


def test_response_operations_404_on_missing_intent(client):
    r = client.post("/api/v1/intents/nope/responses", json={"text": "hi"})
    assert r.status_code == 404
    assert r.json()["error_code"] == "INTENT_NOT_FOUND"


def test_update_missing_response_404(client):
    _create_greet(client)
    r = client.put(
        "/api/v1/intents/greet/responses/9999", json={"text": "x"}
    )
    assert r.status_code == 404
    assert r.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_delete_example(client):
    _create_greet(client)
    example_id = client.get("/api/v1/intents/greet").json()["data"]["examples"][0]["id"]

    r = client.delete(f"/api/v1/intents/greet/examples/{example_id}")
    assert r.status_code == 200

    intent = client.get("/api/v1/intents/greet").json()["data"]
    assert intent["examples"] == []
