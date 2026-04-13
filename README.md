# PlantPal

Indoor plant care tracker built for the EASS course (EX1 + EX2).

Manage your houseplant collection, track watering schedules, and monitor plant health from a single dashboard. Every action is logged so you can look back at your full care history.

## Project Structure

```
PlantPal/
├── backend/                        # FastAPI backend (EX1)
│   ├── app/
│   │   ├── main.py                 # FastAPI app, lifespan, CORS, health
│   │   ├── models.py               # Plant + CareEvent data models
│   │   ├── db.py                   # SQLite / SQLModel setup
│   │   ├── routers/
│   │   │   ├── plants.py           # /plants CRUD endpoints
│   │   │   └── care_events.py      # /care-events endpoints
│   │   └── services/
│   │       ├── plants.py           # Business logic + auto-logging
│   │       └── care_events.py      # Care event queries + creation
│   ├── tests/                      # 49 pytest tests
│   │   ├── conftest.py             # In-memory SQLite fixtures
│   │   └── test_all_endpoints.py   # Full endpoint coverage
│   ├── seed.py                     # Sample data loader (8 plants + 30 events)
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                       # Streamlit dashboard (EX2)
│   ├── plantpal_ui.py              # Main entry point (Dashboard + Add/Edit/Delete)
│   ├── plant_api.py                # HTTP client for the backend
│   ├── cached_api.py               # Cached data layer with TTL
│   ├── care_log.py                 # Care Log page (timeline, drilldown, notes)
│   ├── theme.css                   # Custom green & white theme
│   ├── Dockerfile
│   ├── tests/
│   │   └── test_frontend.py        # 10 frontend tests (mocked, no backend needed)
│   └── requirements.txt
├── docker-compose.yml              # One-command full-stack launch
├── .env.example                    # Environment variable template
└── .gitignore
```

## Quick Start

### Option A: Docker Compose (recommended)

The fastest way to get the full stack running:

```bash
cp .env.example .env                    # create your local env file
sudo docker compose up --build          # builds both images and starts the services
```

> **Note:** Docker commands require `sudo` on most Linux systems unless your user is in the `docker` group.

Once running:

- **Dashboard**: http://localhost:8501
- **API docs (Swagger)**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/health

To seed sample data into the running backend:

```bash
sudo docker compose exec backend uv run python seed.py
```

To stop:

```bash
sudo docker compose down            # stop and remove containers
sudo docker compose down -v         # also delete the persisted SQLite volume
```

#### Changing ports

Edit `.env` before starting:

```env
BACKEND_PORT=9000
FRONTEND_PORT=9501
```

Then run `sudo docker compose up --build`. The dashboard will be at http://localhost:9501 and the API at http://localhost:9000. Internally the containers still use 8000/8501 — only the host-side mappings change.

### Option B: Manual (local development)

#### 1. Backend

```bash
cd backend
uv sync                        # install dependencies
mkdir -p data                  # SQLite database directory
uv run uvicorn app.main:app --reload
```

The API is now at http://localhost:8000. There is no route at `/`, so visiting the root returns 404 — go to http://localhost:8000/docs for the Swagger UI.

Seed sample data (with the API already running):

```bash
uv run python seed.py
```

The seed script reads `API_URL` from the environment (default: `http://localhost:8000`). If your backend runs on a different port:

```bash
API_URL=http://localhost:9000 uv run python seed.py
```

Run backend tests:

```bash
uv run pytest -v               # all 49 tests (in-memory SQLite, no setup needed)
```

#### 2. Frontend

In a second terminal:

```bash
cd frontend
python -m venv .venv                # first time only
source .venv/bin/activate           # activate venv (every new terminal)
pip install -r requirements.txt     # first time only
streamlit run plantpal_ui.py
```

On subsequent runs you only need:

```bash
cd frontend
source .venv/bin/activate
streamlit run plantpal_ui.py
```

> **Linux note:** Modern Debian/Ubuntu block `pip install` outside a venv (PEP 668). The steps above create a local `.venv` to work around this.

Dashboard: http://localhost:8501

#### Pointing to a different backend

By default the frontend connects to `http://localhost:8000`. Set the `API_URL` environment variable to override:

```bash
API_URL=http://localhost:9000 streamlit run plantpal_ui.py
```

When using Docker Compose this is handled automatically — the frontend connects to `http://backend:8000` via the internal Docker network, so no manual `API_URL` is needed.

The sidebar shows a green "Backend connected" or red "Backend unreachable" indicator so you can verify the connection at a glance.

#### CORS configuration

The backend reads allowed origins from the `CORS_ORIGINS` environment variable (comma-separated, default: `http://localhost:8501,http://localhost:5173`). If you change the frontend port, update CORS to match:

```bash
CORS_ORIGINS=http://localhost:9501 uv run uvicorn app.main:app --reload
```

When using Docker Compose, `CORS_ORIGINS` is set automatically based on `FRONTEND_PORT`.

Run frontend tests (no backend needed, uses mocks):

```bash
cd frontend
source .venv/bin/activate
python -m pytest tests/ -v     # all 10 tests
```

## Environment Variables

All configuration is centralized in `.env.example`. Copy it to `.env` and adjust as needed.

| Variable | Default | Used By | Description |
|---|---|---|---|
| `BACKEND_PORT` | `8000` | docker-compose | Host port exposed for the backend API |
| `FRONTEND_PORT` | `8501` | docker-compose | Host port exposed for the Streamlit dashboard |
| `API_URL` | `http://localhost:8000` | frontend, seed.py | URL the frontend (and seed script) use to reach the backend |
| `CORS_ORIGINS` | `http://localhost:8501,http://localhost:5173` | backend | Comma-separated origins allowed by the backend CORS middleware |

**Docker Compose note:** When using `docker compose`, `API_URL` is automatically set to `http://backend:8000` (internal network) and `CORS_ORIGINS` is derived from `FRONTEND_PORT`. You only need to set `BACKEND_PORT` and `FRONTEND_PORT` in your `.env` file.

## Features

### Backend (EX1)

- Full CRUD for plants (`POST`, `GET`, `PUT`, `PATCH`, `DELETE`)
- Care Events API (`GET /care-events/`, `POST /care-events/`) with plant and type filters
- Auto-logging: every watering, health change, and field edit is recorded as a timestamped care event
- Automatic health degradation when plants are overdue for watering
- SQLite persistence via SQLModel
- Health check endpoint (`/health`)
- CORS middleware with configurable origins via `CORS_ORIGINS` env var
- 49 pytest tests using in-memory SQLite (no setup required)
- Seed script with 8 plants and 30 care events covering all field combinations

#### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — returns `{"status": "ok", "service": "plantpal-backend"}` |
| `GET` | `/docs` | Interactive Swagger UI (auto-generated by FastAPI) |
| `POST` | `/plants/` | Create a new plant |
| `GET` | `/plants/` | List all plants (query params: `skip`, `limit`) |
| `GET` | `/plants/{id}` | Get a single plant by ID |
| `PUT` | `/plants/{id}` | Full update — replace all fields |
| `PATCH` | `/plants/{id}` | Partial update (e.g. water a plant, change location) |
| `DELETE` | `/plants/{id}` | Delete a plant |
| `GET` | `/care-events/` | List care events (query params: `plant_id`, `event_type`, `limit`) |
| `POST` | `/care-events/` | Create a care event |

### Frontend (EX2)

- **Dashboard** — card-grid layout showing all plants with:
  - Welcome banner with live garden status summary
  - Glassmorphism stats strip (Total / Healthy / Need Water / Critical)
  - 3-column card grid with health pills, SVG watering countdown rings, and notes preview
  - Pulsing overdue indicators and card hover effects
  - Custom empty state illustration when no plants exist
- **Add / Edit / Delete** — full CRUD through dialog forms
- **Water Now** — one-click watering with automatic event logging
- **Overdue Alerts** — plants past their schedule are flagged with pulsing red dots and card glow
- **Care Log** — full history and insights page:
  - Summary stats: weekly/monthly activity, care streak, most pampered plant
  - Activity timeline grouped by day, filterable by plant and event type
  - Per-plant drilldown with watering count, consistency rating, and full history
  - Add free-text care notes to any plant
  - All edits (name, location, frequency, etc.) appear in the timeline
- **Search and Filter** — sidebar controls to filter by name, location, health, or light need
- **Export to JSON** — download your plant collection as a JSON file (EX2 small extra)
- 10 frontend tests using mocks (no backend needed)

## AI Assistance

This project was built with the help of an AI coding agent (Claude / Cursor) for:

- Project scaffolding and boilerplate
- CRUD service logic and route handlers
- Test cases
- Dashboard layout and styling
- Documentation

All code was reviewed and tested locally. Backend: 49 tests passing. Frontend: 10 tests passing.
