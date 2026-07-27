# Rasa Gate: Architecture Overview

See [README.md](../README.md) for the quickstart. This document covers the
database schema, request flows, and design rules in detail.

## Component diagram

```text
  +---------+         +-----------------+         +--------------+
  |         |  HTTP   |                 |  HTTP   |              |
  | Client  | ------> |   Rasa Gate     | ------> | Rasa Server  |
  |         | <------ |   (FastAPI)     | <------ |              |
  +---------+         +--------+--------+         +--------------+
                               |                          ^
                               | DB Read/Write            |
                               v                          |
                      +------------------+                |
                      |   Rasa Gate DB   |                |
                      | (SQLite/Postgres)|                |
                      +------------------+                |
                               |                           |
                      +------------------+                 |
                      |  Shared Volume   |-----------------+
                      |  - models/*.tar.gz|
                      +------------------+
```

### Components

- **Client:** any HTTP client — a web frontend, mobile app, custom backend
  (PHP, Node.js, Go), curl, or Postman.
- **Rasa Gate (FastAPI):** single entry point handling authentication,
  validation, chat proxying, NLU resource management, and training
  orchestration.
- **Database:** replaces manual YAML editing, ensures safe concurrent data
  entry, and acts as the master record for NLU data.
- **Rasa Server:** standard Rasa Open Source instance that handles NLU
  parsing, dialogue management, and loads trained models from the shared
  `models/` volume.

## Project layout

```text
rasa-gate/
├── app/
│   ├── api/                 # API routers (endpoints)
│   ├── core/                # settings, auth, logging, exceptions
│   ├── db/                  # database engine/session setup
│   ├── models/               # SQLAlchemy ORM models (DB tables)
│   ├── schemas/              # Pydantic request/response validation
│   ├── services/              # business logic & Rasa HTTP calls
│   └── main.py               # FastAPI app instance & entry point
├── examples/
│   └── standalone-rasa-demo/ # unused `rasa init` scaffold, kept for
│                              # reference — see its own README
├── tests/
├── requirements.txt / requirements-dev.txt
└── docker-compose.yml
```

> Note: there is currently no Alembic setup in this repo — schema changes
> happen via `Base.metadata.create_all()` at startup, which is dev-only
> (see Roadmap in the README). If you add Alembic, this is where
> `alembic/` and `alembic.ini` would live.

## Startup lifecycle

On boot, `app/main.py`'s `lifespan` does four things in order:

1. Configure structured logging.
2. Create DB tables if they don't exist (`Base.metadata.create_all` — dev
   only, see the Alembic note above).
3. **Recover stale training tasks:** any task left `pending`/`processing`
   from a previous process (e.g. the server was killed mid-training) is
   marked `failed`, so the training-concurrency guard doesn't stay stuck
   returning 503 forever.
4. **Best-effort Rasa readiness + model preload** (`app/services/rasa_lifecycle.py`):
   poll Rasa's `/status` endpoint until it responds or
   `RASA_STARTUP_MAX_RETRIES` is exhausted, then `PUT` the most recently
   trained model (by file mtime in `RASA_MODEL_PATH`) into Rasa so it's
   ready to serve immediately, without waiting for the next training run.
   This step is **not fatal** — if Rasa isn't reachable, the Gate still
   boots and serves its own CRUD API; only chat/training calls will fail
   until Rasa comes up. Disable entirely with `RASA_STARTUP_WAIT=false`
   (tests do this automatically).

## Core API request flows

### 1. Chat — `POST /api/v1/chat`

```text
Client                Rasa Gate              Rasa Server
  |                      |                       |
  |--- POST /chat ------>|                       |
  |                      |--- POST /webhook ---->|
  |                      |<-- JSON response -----|
  |<-- Standard JSON ----|                       |
```

Client sends `sender_id` and `message`. Rasa Gate forwards it, awaits the
reply, formats it, and returns it.

### 2. Manage NLU data (RESTful CRUD)

Instead of touching YAML directly, clients interact with REST resources.
The API enforces strict naming and handles database cascading
automatically. See the [README API reference](../README.md#api-reference)
for the full endpoint list.

**Data validation & design rules:**

1. **Strict naming:** intent names must not contain spaces or special
   characters. Pydantic enforces `^[a-z0-9_]+$`.
2. **Domain abstraction:** clients never see Rasa's `utter_` prefix. When a
   client adds a response to an intent, Rasa Gate links them in the DB.
   During YAML generation, Rasa Gate prepends `utter_{intent_name}`.

> Altering data via the CRUD API only updates the database. The live model
> is **not** updated until training is triggered.

### 3. Train & reload model — `POST /api/v1/models/train`

Non-blocking, via `BackgroundTasks`.

```text
Client                Rasa Gate              DB                  Rasa Server
  |                      |                       |                   |
  |--- POST /train ----->|                       |                   |
  |<-- 202 Accepted -----|                       |                   |
  | (with task_id)       |                       |                   |
  |                      |--- Compile DB into -->|                   |
  |                      |    single YAML doc    |                   |
  |                      |--------- POST /model/train -------------->|
  |                      |<-------- New model.tar.gz ----------------|
  |                      |                       |                   |
  |                      |--------- PUT /model (Reload) ------------>|
  |                      |<-------- 204 No Content ------------------|
  |                      |                       |                   |
  |                      |--- Update task status in DB               |
```

**Steps:**

1. Client requests training. Rasa Gate returns `202 Accepted` and a
   `task_id` immediately.
2. Background task queries the database and compiles a **single merged
   YAML document** — `recipe`, `assistant_id`, `language`, `intents`,
   `responses`, `nlu`, `rules` — all in one payload (see
   [Training payload format](#training-payload-format) below).
3. Rasa Gate POSTs that payload to Rasa's `/model/train` endpoint.
4. On success, Rasa Gate calls Rasa's `PUT /model` to hot-load the new
   model into memory.
5. Client polls `GET /api/v1/models/train/status/{task_id}`.

#### Model versioning strategy: "Latest only"

Rasa Gate treats trained `.tar.gz` model files as **ephemeral build
artifacts**. No history of trained models is stored — space complexity is
O(1). If a rollback is needed, fix the data via the CRUD API and retrain.
The newest model always overwrites the old one and is loaded immediately.

#### Training payload format

Rasa's `/model/train` endpoint expects **one** YAML document, not a
multi-document `---`-separated stream. Rasa Gate compiles domain, NLU, and
rules into a single dict and dumps it once. Critically, the payload also
includes:

- `recipe` (default: `default.v1`)
- `assistant_id` (default: `rasa-gate-bot`, configurable via `.env`)
- `language` (default: `en`)

These three are required by Rasa 3.x — a payload missing them is rejected.
`pipeline` and `policies` are deliberately omitted so Rasa falls back to
its built-in defaults (equivalent to leaving those sections commented out
in a normal `config.yml`).

#### Stories & rules (auto-generated)

Rasa Gate does **not** support manual story/rule editing in v1.0. Instead,
for every intent *that has at least one response*, a rule is
auto-generated during YAML compilation:

```yaml
rules:
  - rule: Respond to greet
    steps:
      - intent: greet
      - action: utter_greet
```

Intents with no responses get no rule (avoids referencing a nonexistent
`utter_` action).

#### Concurrency

Only one training task may be `pending`/`processing` at a time; a second
request returns `503 TRAINING_IN_PROGRESS`. If the server restarts while a
task is mid-flight, that task is automatically marked `failed` at the next
startup so the queue doesn't stay blocked forever.

## Database schema (SQLAlchemy models)

### Table: `intents`

| Column     | Type        | Constraints                             |
|------------|-------------|------------------------------------------|
| id         | Integer     | Primary Key                             |
| name       | String(255) | Unique, Not Null, Regex: `^[a-z0-9_]+$` |
| description| Text        | Nullable                                |
| created_at | DateTime    | Default: now()                          |
| updated_at | DateTime    | OnUpdate: now()                         |

### Table: `examples`

| Column     | Type     | Constraints                                          |
|------------|----------|-------------------------------------------------------|
| id         | Integer  | Primary Key                                          |
| intent_id  | Integer  | Foreign Key → intents.id (CASCADE DELETE)            |
| text       | Text     | Not Null; unique per intent                          |
| created_at | DateTime | Default: now()                                       |

### Table: `responses`

| Column     | Type     | Constraints                               |
|------------|----------|---------------------------------------------|
| id         | Integer  | Primary Key                               |
| intent_id  | Integer  | Foreign Key → intents.id (CASCADE DELETE) |
| text       | Text     | Not Null                                  |
| created_at | DateTime | Default: now()                            |
| updated_at | DateTime | OnUpdate: now()                           |

### Table: `training_tasks`

| Column        | Type        | Constraints                                          |
|---------------|-------------|--------------------------------------------------------|
| task_id       | String(50)  | Primary Key                                          |
| status        | Enum        | Values: `pending`, `processing`, `success`, `failed`|
| started_at    | DateTime    | Default: now()                                       |
| completed_at  | DateTime    | Nullable                                             |
| error_message | Text        | Nullable                                             |
| webhook_url   | String(500) | Nullable                                             |

**Relationships:**

- `Intent` → `Examples` (One-to-Many, cascade delete)
- `Intent` → `Responses` (One-to-Many, cascade delete)

## Observability & logging

Rasa Gate is designed to be observable in production without forcing heavy
infrastructure dependencies.

1. **Structured logging:** all application logs are output to `stdout` in
   pure JSON format (via `structlog`), natively compatible with log
   aggregators like ELK, Datadog, or Grafana Loki.
2. **Correlation IDs:** every incoming HTTP request is assigned an
   `X-Request-ID`, attached to all DB operations, background tasks, and
   passed downstream to the Rasa server. This gives end-to-end
   traceability of every chat message and training task.

## Testing

```bash
pytest              # all 40 tests, ~1.5s
pytest -v           # verbose
pytest tests/test_training_orchestrator.py   # one file
```

| File | Covers |
|---|---|
| `test_auth.py` | API key middleware: enabled/disabled, missing/wrong/correct key, public routes |
| `test_intents.py` | Intent CRUD, validation, conflicts, cascade delete |
| `test_responses.py` | Response & example sub-resource CRUD |
| `test_chat.py` | Health check, chat proxy (mocked Rasa) |
| `test_training_endpoint.py` | Train trigger (202), one-at-a-time concurrency guard (503), status polling (200/404) |
| `test_training_orchestrator.py` | Full pipeline with a mocked `RasaClient`: success path, failure path, webhook notification |
| `test_training_data.py` | Generated YAML payload: single document, required Rasa config keys, no orphan rules |
| `test_rasa_client.py` | HTTP wrapper: send_message/train/replace_model, error → `RasaUnreachableError` |
| `test_model_persister_and_notifications.py` | Model file writing, webhook payload shape, webhook failures don't propagate |

`tests/conftest.py` gives every test a fresh in-memory SQLite DB via a
`get_db` override, and disables the Rasa startup-readiness wait
(`RASA_STARTUP_WAIT`) automatically so `TestClient(app)` never hangs
waiting for a Rasa server that isn't running.

## HTTP status codes & error handling

See the [README error responses table](../README.md#error-responses) for
the full list and example payload shape.
