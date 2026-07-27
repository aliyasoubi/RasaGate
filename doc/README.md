# Rasa Gate

**A lightweight, self-hosted data-management API for Rasa Open Source.**

Rasa Gate sits between your client apps and a Rasa server. Instead of
hand-editing YAML files, you manage intents, training examples, and bot
responses through a clean REST API backed by a database — then trigger
training with one call and the new model is hot-swapped into Rasa
automatically.

## Why

- Hand-editing `nlu.yml` / `domain.yml` doesn't scale and breaks under
  concurrent edits. Rasa Gate makes a relational database the single source
  of truth.
- Rasa X was deprecated, leaving no lightweight open-source way for
  non-developers or external apps to manage bot content. Rasa Gate fills
  that gap with plain HTTP.

## What it does

1. **Proxies chat** — `POST /api/v1/chat` forwards messages to Rasa and
   standardizes the response envelope.
2. **Manages NLU data** — RESTful CRUD for intents, examples, and responses,
   with validation and cascade deletes.
3. **Orchestrates training** — compiles the database into a single Rasa
   training payload, trains asynchronously in the background, persists the
   model, hot-reloads it into Rasa, and optionally notifies a webhook.

## Quickstart (Docker)

```bash
git clone <your-repo-url> && cd rasa-gate
docker compose up --build
```

Gate: http://localhost:8000 (Swagger UI at `/docs`) · Rasa: http://localhost:5005

Create an intent, train, and chat:

```bash
# 1. Create an intent with examples and responses in one call
curl -X POST http://localhost:8000/api/v1/intents/ \
  -H "Content-Type: application/json" \
  -d '{"name":"greet","examples":["hi","hello","hey there"],"responses":["Hello! How can I help you?"]}'

# 2. Trigger training (returns 202 + task_id)
curl -X POST http://localhost:8000/api/v1/models/train \
  -H "Content-Type: application/json" -d '{}'

# 3. Poll status until "success"
curl http://localhost:8000/api/v1/models/train/status/<task_id>

# 4. Chat
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{"sender_id":"user1","message":"hi"}'
```

## Local development (no Docker)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # adjust RASA_URL if needed
uvicorn app.main:app --reload
pytest                        # run the test suite
```

## API reference

### Chat
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/chat/` | Forward `{sender_id, message}` to Rasa |

### Intents (CRUD)
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/intents/` | List all intents |
| POST | `/api/v1/intents/` | Create intent (optionally with examples + responses) |
| GET | `/api/v1/intents/{name}` | Get one intent |
| PATCH | `/api/v1/intents/{name}` | Update intent description |
| DELETE | `/api/v1/intents/{name}` | Delete intent (cascades to examples & responses) |
| POST | `/api/v1/intents/{name}/examples` | Add a training example |
| PUT | `/api/v1/intents/{name}/examples/{id}` | Edit an example |
| DELETE | `/api/v1/intents/{name}/examples/{id}` | Delete an example |
| POST | `/api/v1/intents/{name}/responses` | Add a response variation |
| PUT | `/api/v1/intents/{name}/responses/{id}` | Edit a response |
| DELETE | `/api/v1/intents/{name}/responses/{id}` | Delete a response |

### Training
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/models/train` | Start async training (202 + `task_id`); optional `{"webhook_url": "..."}` |
| GET | `/api/v1/models/train/status/{task_id}` | Poll task status |

## Design rules

- **Intent naming:** `^[a-z0-9_]+$`, enforced by Pydantic. Invalid names → 400.
- **Domain abstraction:** clients never see Rasa's `utter_` prefix. Response
  variations you add to intent `greet` are grouped under `utter_greet` at
  build time.
- **Auto-generated rules:** for every intent *that has at least one response*,
  a rule `intent → utter_intent` is generated. v1.0 has no manual
  stories/rules editing.
- **Single training payload:** the DB is compiled into ONE merged YAML
  document (domain + nlu + rules) and posted to Rasa's `/model/train` — no
  shared-file editing, no file locking.
- **Latest-only models:** trained `.tar.gz` files are ephemeral build
  artifacts. No model history; to "roll back," fix the data and retrain.
- **One training at a time:** a second train request while one is
  pending/processing returns 503. Tasks stranded by a server restart are
  automatically marked failed at startup.

## Configuration

Copy `.env.example` to `.env`:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./rasa_gate.db` | SQLite for dev, PostgreSQL for prod |
| `RASA_URL` | `http://localhost:5005` | Rasa server base URL |
| `RASA_MODEL_PATH` | `./models` | Where trained models are written (shared with Rasa) |
| `AUTH_TOKEN` | *(empty)* | If set, all `/api/*` routes require header `X-API-Key: <token>` |
| `LOG_LEVEL` | `INFO` | Structured JSON logs via structlog |

## Error responses

All errors share one envelope:

```json
{
  "status": "error",
  "error_code": "INTENT_ALREADY_EXISTS",
  "message": "Intent 'greet' already exists.",
  "details": {"intent_name": "greet"}
}
```

| Status | When |
|---|---|
| 400 | Validation failure (e.g. intent name with spaces) |
| 401 | Missing/invalid `X-API-Key` (when auth enabled) |
| 404 | Intent / example / response / task not found |
| 409 | Intent name already exists |
| 500 | Rasa unreachable or internal failure |
| 503 | Training already in progress |

## Architecture

```text
  +---------+         +-----------------+         +--------------+
  | Client  | ------> |   Rasa Gate     | ------> | Rasa Server  |
  |         | <------ |   (FastAPI)     | <------ |  (3.6.x)     |
  +---------+         +--------+--------+         +------+-------+
                               |                         |
                        DB read/write            shared ./models
                               v                  volume (tar.gz)
                      +------------------+              |
                      |   Rasa Gate DB   |              |
                      | (SQLite/Postgres)|<-------------+
                      +------------------+   hot-swap via PUT /model
```

Stack: FastAPI · Pydantic v2 · SQLAlchemy 2.0 · httpx · structlog.
Observability: JSON logs to stdout, `X-Request-ID` correlation on every request.

## Roadmap

- Entity / slot annotation support
- Manual stories & rules editing
- Web admin UI (intent editor + train button + chat test widget)
- Alembic migrations for production schema changes
- Pagination on list endpoints
