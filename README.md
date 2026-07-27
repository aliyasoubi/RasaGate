# Rasa Gate

**A lightweight, self-hosted data-management API for Rasa Open Source.**

Rasa Gate sits between your client apps and a Rasa server. Instead of
hand-editing YAML files, you manage intents, training examples, and bot
responses through a clean REST API backed by a database — then trigger
training with one call and the new model is hot-swapped into Rasa
automatically.

Full design rationale, database schema, and request-flow diagrams live in
**[ARCHITECTURE.md](doc/ARCHITECTURE.md)**.

## Why

- Hand-editing `nlu.yml` / `domain.yml` doesn't scale and breaks under
  concurrent edits. Rasa Gate makes a relational database the single source
  of truth.
- Rasa X was deprecated, leaving no lightweight open-source way for
  non-developers or external apps to manage bot content. Rasa Gate fills
  that gap with plain HTTP.

## Quickstart (Docker)

```bash
git clone <your-repo-url> && cd rasa-gate
docker compose up --build
```

Gate: http://localhost:8000 (Swagger UI at `/docs`) · Rasa: http://localhost:5005

On startup, the Gate waits for Rasa to become reachable and preloads the
most recently trained model (if `./models` has one) so a restart doesn't
leave Rasa idle. This is best-effort — if Rasa isn't up yet, the Gate still
boots and serves its own CRUD API; chat/training calls will just fail until
Rasa is reachable.

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

> If you're not also running a local Rasa server, set `RASA_STARTUP_WAIT=false`
> in `.env` — otherwise the Gate will spend up to `RASA_STARTUP_MAX_RETRIES *
> RASA_STARTUP_RETRY_DELAY` seconds waiting for Rasa on every startup before
> giving up and continuing anyway.

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

## Configuration

Copy `.env.example` to `.env`:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./rasa_gate.db` | SQLite for dev, PostgreSQL for prod |
| `RASA_URL` | `http://localhost:5005` | Rasa server base URL |
| `RASA_MODEL_PATH` | `./models` | Where trained models are written (shared with Rasa) |
| `RASA_RECIPE` | `default.v1` | Rasa training recipe, sent with every training payload |
| `RASA_ASSISTANT_ID` | `rasa-gate-bot` | Required by Rasa 3.x; set uniquely per deployment |
| `RASA_LANGUAGE` | `en` | NLU pipeline language |
| `RASA_STARTUP_WAIT` | `true` | Wait for Rasa + preload latest model at startup (set `false` if running the Gate without Rasa) |
| `RASA_STARTUP_MAX_RETRIES` | `15` | Startup readiness check attempts before giving up (non-fatal) |
| `RASA_STARTUP_RETRY_DELAY` | `2.0` | Seconds between readiness checks |
| `AUTH_TOKEN` | *(empty)* | If set, all `/api/*` routes require header `X-API-Key: <token>` |
| `LOG_LEVEL` | `INFO` | Structured JSON logs via structlog |

### Why auth matters

With `AUTH_TOKEN` unset, **anyone who can reach the server can read, edit,
or delete every intent, trigger training on demand, and send chat messages
as any user** — there's no login screen in front of this API. That's fine
for local development on your own machine. The moment the Gate is reachable
by anyone else (a shared dev box, staging, production), set `AUTH_TOKEN` and
have your client apps send it as `X-API-Key`. It's a single shared secret
(not per-user accounts) because Rasa Gate is a backend-to-backend gateway —
end users never see the key directly.

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

## Roadmap

- Entity / slot annotation support
- Manual stories & rules editing
- Web admin UI (intent editor + train button + chat test widget)
- Alembic migrations for production schema changes
- Pagination on list endpoints
