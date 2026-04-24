# PlantPal

Indoor plant care tracker — EASS course project (EX1 + EX2 + EX3).

Track your houseplants, log waterings, monitor health, get AI care tips,
and let a background worker keep health statuses fresh automatically.

---

## Table of contents

1. [Prerequisites](#prerequisites)
2. [Quick start — Docker Compose (recommended)](#quick-start--docker-compose-recommended)
3. [Quick start — no Docker (manual)](#quick-start--no-docker-manual)
4. [Seed sample data](#seed-sample-data)
5. [Using the Streamlit dashboard](#using-the-streamlit-dashboard)
6. [Using the Typer CLI](#using-the-typer-cli)
7. [AI advice — rule-based vs Google Gemini](#ai-advice--rule-based-vs-google-gemini)
8. [Running the async refresher](#running-the-async-refresher)
9. [Authentication](#authentication)
10. [Running tests](#running-tests)
11. [API reference](#api-reference)
12. [Environment variables](#environment-variables)
13. [Project structure](#project-structure)
14. [AI Assistance](#ai-assistance)

---

## Prerequisites

| Tool | Min version | Install |
|------|-------------|---------|
| Docker + Compose | 24+ | https://docs.docker.com/get-docker/ |
| Python | 3.11+ | https://python.org |
| `uv` (Python package manager) | any | `pip install uv` or https://docs.astral.sh/uv |

Docker requires `sudo` on most Linux systems unless your user is in the
`docker` group.

---

## Quick start — Docker Compose (recommended)

This starts the full EX3 stack: backend, Streamlit dashboard, AI advisor,
Redis, and the background health-refresh worker.

```bash
# 1. Copy the environment template (only needed once)
cp .env.example .env

# 2. Build images and start all five services
sudo docker compose -f compose.yaml up --build
```

Wait until the terminal shows all services healthy (about 30 seconds on
first run). You will see lines like:

```
plantpal-redis    | Ready to accept connections
plantpal-backend  | Application startup complete.
plantpal-ai       | Application startup complete.
plantpal-frontend | You can now view your Streamlit app in your browser.
```

Then open:

| What | URL |
|------|-----|
| **Streamlit dashboard** | http://localhost:8501 |
| **Swagger / API docs** | http://localhost:8000/docs |
| **AI advisor health** | http://localhost:8001/health |
| **Backend health** | http://localhost:8000/health |

> **Note:** the dashboard is empty until you seed data — see below.

### Seed sample data

In a second terminal while the stack is running:

```bash
sudo docker compose -f compose.yaml exec backend uv run python seed.py
```

This creates 8 plants (Monstera, Basil, Peace Lily, etc.) plus 30 care
events covering every health status, location, and light level.
It is **idempotent** — safe to run again, it skips if data already exists.

### Stop the stack

```bash
sudo docker compose -f compose.yaml down         # stop, keep data volume
sudo docker compose -f compose.yaml down -v      # stop and delete data
```

---

## Quick start — no Docker (manual)

Use this when you want faster iteration without rebuilding images.
You need **four terminals**.

### Terminal 1 — Redis

```bash
# Option A: Docker single-container (easiest)
sudo docker run -d --name plantpal-redis -p 6379:6379 redis:7-alpine

# Option B: local Redis if installed
redis-server
```

> Redis is optional — the backend degrades gracefully without it
> (no caching, no rate limiting, no idempotency). Skip if you just
> want to test the core API.

### Terminal 2 — AI advisor service

```bash
cd ai_service
# Reuse the backend venv (fastest) or create a dedicated one:
pip install -r requirements.txt  # inside a venv

# Start on port 8001
uvicorn main:app --port 8001 --reload
```

> Also optional — the backend falls back to rule-based advice if the
> AI service is unreachable.

### Terminal 3 — Backend

```bash
cd backend
uv sync                          # install dependencies (first time only)
mkdir -p data                    # SQLite database directory
uv run uvicorn app.main:app --reload
```

Verify it is running:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"plantpal-backend"}
```

Seed data (while backend is running):

```bash
cd backend
uv run python seed.py
```

### Terminal 4 — Streamlit dashboard

```bash
cd frontend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # first time only
streamlit run plantpal_ui.py
```

Dashboard: http://localhost:8501

The sidebar shows a green "Backend connected" or red "Backend unreachable"
indicator.

---

## Using the Streamlit dashboard

The dashboard is the primary EX2 interface. After seeding you will see:

- **Stats strip** — total plants, healthy count, need-water count, critical count
- **Plant cards** — health pill, SVG watering countdown ring, location/light info
- **Overdue alerts** — red pulsing dot on cards that are past their schedule

### Action buttons on each card

| Button | What it does |
|--------|-------------|
| 💧 | Water the plant now (sets `last_watered` to now, auto-heals health if unhealthy) |
| ✏️ | Open edit dialog to change any field |
| 🗑️ | Delete the plant (with confirmation) |
| 🤖 | Fetch AI care advice for this specific plant |

### Other features

- **➕ Add Plant** — button at the top of the dashboard
- **Search + Filters** — sidebar controls (by name, location, health, light)
- **Care Log** — second page (sidebar radio): full event timeline grouped by
  day, per-plant drilldown, consistency rating, and a free-text notes form
- **📥 Export to JSON** — download button at the bottom of the dashboard

---

## Using the Typer CLI

The CLI (`scripts/plantpal_cli.py`) is the EX2 Typer interface and also
provides the EX3 CSV enhancement. It talks to the same backend API.

### Setup (no Docker)

The CLI uses the backend's virtual environment:

```bash
cd /path/to/PlantPal         # repo root
# backend venv must exist (uv sync inside backend/ creates it)
```

### Commands

**List all plants:**

```bash
python scripts/plantpal_cli.py list-plants
```

**Log in and get a JWT:**

```bash
TOKEN=$(python scripts/plantpal_cli.py login \
  --username gardener --password plantpal)
echo $TOKEN
```

**Add a plant (requires editor token):**

```bash
PLANTPAL_TOKEN=$TOKEN python scripts/plantpal_cli.py add-plant \
  --name "Spider Plant" --species "Chlorophytum comosum" \
  --location "Office" --frequency 120
```

**Export the catalog to CSV:**

```bash
python scripts/plantpal_cli.py export-csv --output plants.csv
```

**Import plants from a CSV file (requires editor token):**

```bash
PLANTPAL_TOKEN=$TOKEN python scripts/plantpal_cli.py import-csv plants.csv
```

**Get AI advice for plant ID 1:**

```bash
python scripts/plantpal_cli.py advice 1
```

**Point at a non-default backend URL:**

```bash
python scripts/plantpal_cli.py list-plants --api-url http://localhost:9000
```

---

## AI advice — rule-based vs Google Gemini

The `ai_service` runs as a separate FastAPI microservice on port 8001.
It has two operating modes:

### Mode 1 — Rule-based (default, no setup needed)

Works out of the box, no API keys required. The service reads the plant's
`health_status`, `light_need`, `water_frequency_hours`, and `location`
and returns deterministic tips. Source is shown as `"rule-based"` in the
response.

```bash
curl http://localhost:8000/plants/1/advice
```

```json
{
  "plant_id": 1,
  "plant_name": "Monstera",
  "summary": "Care tips for Monstera (Monstera deliciosa).",
  "tips": [
    "Keep following the current schedule — looking good!",
    "Medium indirect light suits this plant well.",
    "Let the top inch of soil dry out between waterings."
  ],
  "source": "rule-based"
}
```

### Mode 2 — Google Gemini (real LLM, optional)

Set two environment variables and the service automatically switches to
Pydantic AI + Google Gemini for richer, plant-specific advice.

**Step 1 — Get a free API key:**

1. Go to https://aistudio.google.com/
2. Click **Get API key** → **Create API key**
3. Copy the key

**Step 2 — Add to your `.env`:**

```ini
GOOGLE_API_KEY=your-key-here
GOOGLE_GEMINI_MODEL=gemini-1.5-flash
```

`gemini-1.5-flash` is the recommended model — it is fast and free-tier
friendly. You can also use `gemini-1.5-pro` for longer responses.

**Step 3 — Restart the AI service:**

```bash
# With Docker Compose
sudo docker compose -f compose.yaml up --build ai_service

# Without Docker — just restart Terminal 2 after editing .env
```

**Step 4 — Verify it is using Gemini:**

```bash
curl http://localhost:8000/plants/1/advice | python3 -m json.tool
```

The response will show `"source": "gemini"` instead of `"rule-based"`.

**In the Streamlit dashboard**, click the **🤖** button on any plant card
to see the advice panel appear below the card — no page reload needed.

> **No API key?** The service silently falls back to rule-based mode.
> The stack always works end-to-end.

---

## Running the async refresher

The refresher (`scripts/refresh.py`) re-evaluates the health status for
every plant in the background using bounded async concurrency and Redis
idempotency keys so it never processes the same plant twice in one day.

```bash
# Refresh up to 10 plants (default)
python scripts/refresh.py --limit 10

# Refresh all 50, point at a custom backend
python scripts/refresh.py --limit 50 --api-url http://localhost:8000
```

**With Docker Compose** the worker service runs this loop automatically
every 5 minutes. You can also trigger it manually:

```bash
sudo docker compose -f compose.yaml exec worker \
  uv run python /workspace/scripts/refresh.py --limit 50 \
  --api-url http://backend:8000
```

**Expected log output** (first run — all processed):

```
INFO [plantpal.refresh] starting trace_id=plantpal-refresh-f5ca1873 jobs=8
INFO [plantpal.refresh] refreshed plant_id=1 idempotency_key=plant-health:1:2026-04-24
INFO [plantpal.refresh] refreshed plant_id=2 idempotency_key=plant-health:2:2026-04-24
...
INFO [plantpal.refresh] done summary={'processed': 8, 'skipped_duplicate': 0, 'total': 8}
```

**Run again immediately** — Redis idempotency keys prevent duplicate work:

```
INFO [plantpal.refresh] done summary={'processed': 0, 'skipped_duplicate': 8, 'total': 8}
```

---

## Authentication

Write operations (add, edit, delete, water plants) require an editor JWT.
**The Streamlit dashboard handles this automatically** — it logs in with
the default credentials on startup and stores the token in session state.

### Default dev credentials

| Username | Password | Role |
|----------|----------|------|
| `gardener` | `plantpal` | editor (can read + write) |
| `viewer` | `viewer` | viewer (read-only) |

### Get a token manually (curl)

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=gardener&password=plantpal" | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token: ${TOKEN:0:30}..."
```

Use it:

```bash
# Create a plant
curl -X POST http://localhost:8000/plants/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Cactus","species":"Cactaceae"}'

# No token → 401
curl -X POST http://localhost:8000/plants/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Fail","species":"x"}'

# Viewer token → 403
```

> Read routes (`GET /plants/`, `GET /plants/{id}`, `GET /care-events/`)
> are **public** — no token needed. Only writes are protected.

---

## Running tests

Each test suite is independent and uses mocks/in-memory DBs — no running
server needed.

### Backend (59 tests)

```bash
cd backend
uv run pytest -v
# With coverage report:
uv run pytest --cov=app --cov-report=term-missing
```

### CLI + async refresher (6 tests)

Run from the repo root using the backend's venv:

```bash
backend/.venv/bin/python -m pytest scripts/tests/ -v
```

### AI service (3 tests)

```bash
cd ai_service
/path/to/PlantPal/backend/.venv/bin/python -m pytest tests/ -v
```

### Frontend (10 tests)

```bash
cd frontend
# First time: create venv
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m pytest tests/ -v
```

### Run everything at once

```bash
cd /path/to/PlantPal

echo "--- Backend ---"
backend/.venv/bin/python -m pytest backend/tests/ -q

echo "--- Scripts ---"
backend/.venv/bin/python -m pytest scripts/tests/ -q

echo "--- AI service ---"
cd ai_service && ../backend/.venv/bin/python -m pytest tests/ -q && cd ..

echo "--- Frontend ---"
cd frontend && .venv/bin/python -m pytest tests/ -q && cd ..
```

Expected: **78 tests, all passing**.

---

## API reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | — | Service health check |
| `POST` | `/token` | — | Login — returns `access_token` JWT |
| `GET` | `/plants/` | — | List all plants (Redis-cached 60 s) |
| `GET` | `/plants/{id}` | — | Get one plant |
| `GET` | `/plants/{id}/advice` | — | AI care tips (Gemini or rule-based) |
| `POST` | `/plants/` | editor | Create a plant |
| `PUT` | `/plants/{id}` | editor | Full replace |
| `PATCH` | `/plants/{id}` | editor | Partial update (e.g. water) |
| `DELETE` | `/plants/{id}` | editor | Delete |
| `GET` | `/care-events/` | — | List care events (filter by `plant_id`, `event_type`) |
| `POST` | `/care-events/` | — | Create a care event |

Full interactive docs: http://localhost:8000/docs

---

## Environment variables

Copy `.env.example` to `.env` and adjust. Docker Compose reads it
automatically.

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_PORT` | `8000` | Host port for the backend |
| `FRONTEND_PORT` | `8501` | Host port for the Streamlit dashboard |
| `AI_PORT` | `8001` | Host port for the AI advisor |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `RATE_LIMIT_PER_MINUTE` | `60` | Max requests per IP per path per minute |
| `AI_SERVICE_URL` | `http://localhost:8001` | Backend → AI service URL |
| `GOOGLE_API_KEY` | *(empty)* | Google AI Studio key — enables Gemini mode |
| `GOOGLE_GEMINI_MODEL` | *(empty)* | Model name, e.g. `gemini-1.5-flash` |
| `JWT_SECRET` | placeholder | HS256 signing key — **change before deploying** |
| `JWT_EXPIRY_MINUTES` | `30` | Token lifetime in minutes |
| `DEFAULT_EDITOR_USERNAME` | `gardener` | Dev editor username |
| `DEFAULT_EDITOR_PASSWORD` | `plantpal` | Dev editor password |

---

## Project structure

```
PlantPal/
├── backend/                    # FastAPI + SQLModel/SQLite (EX1)
│   ├── app/
│   │   ├── main.py             # App factory, CORS, middleware
│   │   ├── config.py           # pydantic-settings (all env vars)
│   │   ├── cache.py            # Redis helpers (get/set/invalidate)
│   │   ├── rate_limit.py       # Per-IP rate-limit middleware
│   │   ├── security.py         # bcrypt hashing + JWT issue/verify
│   │   ├── models.py           # Plant + CareEvent SQLModel schemas
│   │   ├── db.py               # SQLite engine + session dep
│   │   ├── routers/
│   │   │   ├── auth.py         # POST /token
│   │   │   ├── plants.py       # /plants CRUD + /advice proxy
│   │   │   └── care_events.py  # /care-events
│   │   └── services/
│   │       ├── plants.py       # Business logic, health degradation
│   │       ├── care_events.py  # Event queries + creation
│   │       └── advice.py       # Calls ai_service, fallback logic
│   ├── tests/                  # 59 tests (endpoints + security)
│   ├── seed.py                 # 8 plants + 30 care events
│   ├── Dockerfile
│   └── pyproject.toml
│
├── frontend/                   # Streamlit dashboard (EX2)
│   ├── plantpal_ui.py          # Dashboard page (cards, dialogs)
│   ├── plant_api.py            # HTTP client with JWT auto-login
│   ├── cached_api.py           # TTL cache wrapper
│   ├── care_log.py             # Care Log page
│   ├── theme.css               # Green + glassmorphism styling
│   ├── tests/                  # 10 mocked tests
│   └── requirements.txt
│
├── ai_service/                 # Plant care advisor (EX3 4th service)
│   ├── main.py                 # POST /advice (Gemini or rule-based)
│   ├── tests/                  # 3 tests
│   ├── requirements.txt
│   └── Dockerfile
│
├── scripts/                    # CLI + tooling (EX2 + EX3)
│   ├── plantpal_cli.py         # Typer CLI: list/add/export/import/advice/login
│   ├── refresh.py              # Async health refresher
│   ├── demo.sh                 # End-to-end walkthrough script
│   └── tests/                  # 6 tests (CliRunner + anyio)
│
├── docs/
│   ├── EX3-notes.md            # Course deliverable notes + trace excerpts
│   ├── security-checklist.md   # OWASP controls + rotation steps
│   └── runbooks/compose.md     # Step-by-step Compose operations
│
├── .github/workflows/ci.yml    # CI: Redis + pytest --cov + Schemathesis
├── compose.yaml                # Full EX3 stack (5 services)
├── docker-compose.yml          # Legacy EX2 stack (2 services)
├── .env.example                # All env variables with defaults
└── .gitignore
```

---

## AI Assistance

Built with Claude / Cursor AI agent for:

- EX1 scaffolding: FastAPI, SQLModel, CRUD, health degradation logic
- EX2 scaffolding: Streamlit dashboard, care log, CSS theme
- EX3 additions: Redis cache + rate-limit middleware, JWT security, async
  refresher with tenacity, AI advisor microservice with Pydantic AI,
  Typer CLI with CSV export/import, Docker Compose upgrade, CI pipeline
- Test cases for all layers

All prompts were based on the course session notes (Sessions 05–11) and
the EX rubrics. Every generated file was reviewed, run locally, and
verified by the test suite before committing.

Test counts: backend 59 · AI service 3 · scripts 6 · frontend 10 = **78 total**.
