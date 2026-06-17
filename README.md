# Rasa Gate v1.0: Architecture Overview

## What Is Rasa Gate?

Rasa Gate is a robust proxy and management API built with FastAPI. It sits between your client applications and the Rasa
server.

Instead of directly editing Rasa's configuration files, Rasa Gate utilizes a relational database as the single source of
truth to prevent file-locking and concurrency issues. It performs three main tasks:

1. **Proxies chat messages** securely to Rasa and standardizes the responses.
2. **Manages NLU and Domain data** via standard RESTful CRUD endpoints backed by a database.
3. **Orchestrates asynchronous model training** and hot-reloads the updated model into Rasa's memory.

---

## Recommended Best Practice Tech Stack

To implement this architecture effectively, the following stack is recommended:

* **Web Framework:** **FastAPI** (for high performance, async support, and auto-generated Swagger UI).
* **Data Validation:** **Pydantic V2** (for strict input schemas and regex validation).
* **Database ORM:** **SQLAlchemy 2.0** (for interacting with the database using Python objects).
* **Database Engine:** **PostgreSQL** (Production) or **SQLite** (Development/Testing).
* **Database Migrations:** **Alembic** (to track changes to the database schema over time).
* **Asynchronous Tasks:** FastAPI's built-in **`BackgroundTasks`** (sufficient for standard training, upgradable to *
  *Celery** + Redis if training queues become highly complex).

---
# Project Folder Architecture

For a scalable and maintainable FastAPI project, we use a domain-driven, layered architecture.

```text
rasa-gate/
├── app/
│   ├── api/                 # API Routers (Endpoints)
│   ├── core/                # App-wide settings and configs
│   ├── db/                  # Database setup and sessions
│   ├── models/              # SQLAlchemy ORM Models (Database Tables)
│   ├── schemas/             # Pydantic Models (Request/Response Validation)
│   ├── services/            # Business Logic & External API Calls
│   └── main.py              # FastAPI application instance & entry point
├── alembic/                 # Database migration scripts
├── alembic.ini              # Alembic configuration
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables
└── README.md
```
---
## Component Diagram & Architecture

```text
  +---------+         +-----------------+         +--------------+
  |         |  HTTP   |                 |  HTTP   |              |
  | Client  | ------> |   Rasa Gate     | ------> | Rasa Server  |
  |         | <------ |   (FastAPI)     | <------ |              |
  +---------+         +--------+--------+         +--------------+
                               |                          ^
                               | DB Read/Write &          |
                               | YAML Generation          |
                               v                          |
                      +------------------+                |
                      |   Rasa Gate DB   |                |
                      | (SQLite/Postgres)|                |
                      +------------------+                |
                      |  Shared Volume   |----------------+
                      |  - nlu.yml       |
                      |  - domain.yml    |
                      +------------------+
```

### Components

- **Client:** Any HTTP client: a web frontend, mobile app, custom backend (PHP, Node.js, Go), curl, or Postman.
- **Rasa Gate (FastAPI):** Single entry point handling authentication, validation, chat proxying, database NLU resource
  management, and YAML generation/training orchestration.
- **Database:** Replaces manual YAML editing, ensures safe concurrent data entry, and acts as the master record for NLU
  data.
- **Rasa Server:** Standard Rasa Open Source instance that handles NLU parsing, dialogue management, and reads YAML from
  the shared Docker volume.

---

## Core API Request Flows & Design Rules

### 1. Chat — `POST /api/v1/chat`

```text
Client                Rasa Gate              Rasa Server
  |                      |                       |
  |--- POST /chat ------>|                       |
  |                      |--- POST /webhook ---->|
  |                      |<-- JSON response -----|
  |<-- Standard JSON ----|                       |
*Client sends `sender_id` and `message`. Rasa Gate forwards it, awaits the reply, formats it, and returns it securely.*
```

---

### 2. Manage NLU Data (RESTful CRUD)

Instead of touching YAML directly, clients interact with REST resources. The API enforces strict naming, allows for easy editing, and handles database cascading automatically.

#### Endpoints

- **Create/Read:**
- `GET /api/v1/intents`
- `POST /api/v1/intents` *(Can accept intent, examples, and responses in one payload)*
- `POST /api/v1/intents/{intent_name}/examples`
- `POST /api/v1/intents/{intent_name}/responses`
- **Update/Edit:**
- `PUT /api/v1/intents/{intent_name}` *(Rename the intent; automatically updates linked `utter_` responses)*
- `PUT /api/v1/intents/{intent_name}/examples/{example_id}` *(Edit a specific training phrase)*
- `PUT /api/v1/intents/{intent_name}/responses/{response_id}` *(Edit a specific bot response)*
- **Delete (with Cascading):**
- `DELETE /api/v1/intents/{intent_name}` *(Deletes the intent AND automatically cascades to delete all of its linked examples and domain responses)*
- `DELETE /api/v1/intents/{intent_name}/examples/{example_id}` *(Deletes a specific training phrase only)*

#### Data Validation & Design Rules

1. **Strict Naming Rules:** Intent names must not contain spaces or special characters. Pydantic enforces a regex pattern: `^[a-z0-9_]+$`.
2. **Domain Abstraction:** Clients do not need to know about Rasa's `utter_` prefix. When a client adds a "response" to an intent, Rasa Gate links them in the DB. During YAML generation, Rasa Gate automatically prepends `utter_{intent_name}` to construct the `domain.yml` file.

*> Note: Altering data via the CRUD API only updates the database. The live model is **not** updated until training is triggered.*


---

### 3. Train & Reload Model — `POST /api/v1/models/train`

This is a non-blocking operation utilizing asynchronous background tasks.

#### Model Versioning Strategy: "Latest Only"

Rasa Gate treats YAML files and trained `.tar.gz` model files as **ephemeral build artifacts**. We do not store a history of trained models. Space complexity is kept at $O(1)$. If a rollback is needed, the user corrects the data via the CRUD API and retrains. The newest model always overwrites the old one and is immediately loaded into memory.

```text
Client                Rasa Gate              DB / Files          Rasa Server
  |                      |                       |                   |
  |--- POST /train ----->|                       |                   |
  |<-- 202 Accepted -----|                       |                   |
  | (with task_id)       |                       |                   |
  |                      |--- Dump DB to YAML -->|                   |
  |                      |                       |                   |
  |                      |--------- POST /model/train -------------->|
  |                      |<-------- New model.tar.gz ----------------|
  |                      |                       |                   |
  |                      |--------- PUT /model (Reload) ------------>|
  |                      |<-------- 204 No Content ------------------|
  |                      |                       |                   |
  |                      |--- Update task status in DB               |
```

**Steps:**

1. Client requests training. Rasa Gate returns `202 Accepted` and a `task_id` immediately.
2. Background task queries the database and generates clean `nlu.yml` and `domain.yml` files in the shared volume.
3. Rasa Gate calls Rasa's `/model/train` endpoint.
4. Upon successful training, Rasa Gate calls Rasa's `PUT /model` to load the newly created model into memory.
5. Client polls `GET /api/v1/models/train/status/{task_id}` to know when the bot is ready.

## Database Schema (SQLAlchemy Models)

### Table: `intents`

| Column     | Type        | Constraints                             |
|------------|-------------|-----------------------------------------|
| id         | Integer     | Primary Key                             |
| name       | String(100) | Unique, Not Null, Regex: `^[a-z0-9_]+$` |
| created_at | DateTime    | Default: now()                          |
| updated_at | DateTime    | OnUpdate: now()                         |

### Table: `examples`

| Column     | Type     | Constraints                               |
|------------|----------|-------------------------------------------|
| id         | Integer  | Primary Key                               |
| intent_id  | Integer  | Foreign Key → intents.id (CASCADE DELETE) |
| text       | Text     | Not Null                                  |
| created_at | DateTime | Default: now()                            |

### Table: `responses`

| Column     | Type     | Constraints                               |
|------------|----------|-------------------------------------------|
| id         | Integer  | Primary Key                               |
| intent_id  | Integer  | Foreign Key → intents.id (CASCADE DELETE) |
| text       | Text     | Not Null                                  |
| created_at | DateTime | Default: now()                            |

### Table: `training_tasks`

| Column        | Type        | Constraints                                          |
|---------------|-------------|------------------------------------------------------|
| task_id       | String(50)  | Primary Key                                          |
| status        | Enum        | Values: `pending`, `processing`, `success`, `failed` |
| started_at    | DateTime    | Default: now()                                       |
| completed_at  | DateTime    | Nullable                                             |
| error_message | Text        | Nullable                                             |
| webhook_url   | String(500) | Nullable                                             |

**Relationships:**

- `Intent` → `Examples` (One-to-Many, Cascade Delete)
- `Intent` → `Responses` (One-to-Many, Cascade Delete)

---

## Response Management & Stories Auto-Generation

**Design Rule:** Each intent has exactly **one** response action named `utter_{intent_name}`.

- When a client creates an intent `greet`, Rasa Gate automatically creates a response action `utter_greet` in the
  domain.
- Clients can add **multiple text variations** to `utter_greet` (stored in the `responses` table).
- During YAML generation, all variations are grouped under the same `utter_` key.

**Example domain.yml output:**

```yaml
responses:
  utter_greet:
    - text: "Hello! How can I help you?"
    - text: "Hi there!"
```

**Client API abstraction:** Clients never see `utter_` prefixes. They just POST to `/api/v1/intents/greet/responses`.


---

### 3. **Stories & Rules Auto-Generation**

You mention it briefly but don't explain the logic:

## Stories & Rules (Auto-Generated)

Rasa Gate **does not** support manual story/rule editing in v1.0. Instead:

- For every intent, a simple rule is auto-generated during YAML dump:

```yaml
  rules:
    - rule: Respond to greet
  steps:
    - intent: greet
    - action: utter_greet
```  

---

### 4. **Error Handling & HTTP Status Codes**

Add a reference table:

## HTTP Status Codes & Error Handling

| Status                    | Scenario                                      |
|---------------------------|-----------------------------------------------|
| 200 OK                    | Successful GET/PUT/DELETE                     |
| 201 Created               | Successful POST (resource created)            |
| 202 Accepted              | Training started (async task)                 |
| 400 Bad Request           | Invalid input (e.g., intent name with spaces) |
| 404 Not Found             | Intent/Example/Response not found             |
| 409 Conflict              | Intent name already exists                    |
| 500 Internal Server Error | Rasa server unreachable or DB failure         |
| 503 Service Unavailable   | Training already in progress                  |

**Error Response Example:**

```json
{
  "status": "error",
  "error_code": "INTENT_NAME_INVALID",
  "message": "Intent name must match pattern: ^[a-z0-9_]+$",
  "details": {
    "field": "name",
    "provided_value": "greet user!"
  }
}
```

---

## Observability & Logging

Rasa Gate is designed to be highly observable for production environments without forcing heavy infrastructure
dependencies.

1. **Structured Logging:** All application logs are output to `stdout` in pure JSON format (using `structlog`). This
   makes Rasa Gate natively compatible with log aggregators like ELK (Elasticsearch/Logstash/Kibana), Datadog, or
   Grafana Loki.
2. **Correlation IDs:** Every incoming HTTP request is assigned an `X-Request-ID`. This Correlation ID is attached to
   all database operations, background tasks, and is passed downstream to the Rasa Server headers. This ensures complete
   end-to-end traceability of every chat message and training task.

---

### 5. **Environment Variables & Configuration**

Add a `.env` example:

## Environment Configuration

**`.env` file:**

```env
APP_HOST=0.0.0.0
APP_PORT=8000
APP_DEBUG=True
LOG_LEVEL=INFO

DATABASE_URL=sqlite:///./rasa_gate.db

RASA_URL=http://localhost:5005
RASA_MODEL_PATH=./models
AUTH_TOKEN=
```
## Installation

1. **Clone the repository:**
```bash
   git clone <your-repo-url>
   cd rasa-gate
```

2. **Create and activate a virtual environment:**
```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash   
  pip install -r requirements.txt
```
4. **Run the application:**
```bash   
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```