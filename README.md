# PlantPal — Indoor Plant Care Tracker

A monorepo for the EASS course (EX1 + EX2). PlantPal helps you manage your houseplant collection, track watering schedules, and monitor plant health — all from a single dashboard.

## Project Structure

```
EASS-HIT/
├── backend/                        # EX1 – FastAPI backend
│   ├── app/
│   │   ├── models.py               # Plant + CareEvent data models
│   │   ├── routers/
│   │   │   ├── plants.py           # /plants CRUD endpoints
│   │   │   └── care_events.py      # /care-events endpoints
│   │   ├── services/
│   │   │   ├── plants.py           # Plant business logic + auto-logging
│   │   │   └── care_events.py      # Care event queries + creation
│   │   └── db.py                   # SQLite / SQLModel setup
│   ├── tests/                      # pytest test suite (31 tests)
│   │   ├── test_plants.py          # Plant CRUD + auto-logging tests
│   │   ├── test_care_events.py     # Care event endpoint tests
│   │   └── test_smoke.py           # Health / docs smoke tests
│   ├── seed.py                     # Sample data loader
│   └── README.md                   # Backend-specific docs
├── frontend/                       # EX2 – Streamlit dashboard
│   ├── plantpal_ui.py              # Main entry point
│   ├── plant_api.py                # HTTP client for the backend
│   ├── cached_api.py               # Cached data layer
│   ├── care_log.py                 # Care Log page (timeline + insights)
│   └── tests/                      # Frontend workflow tests
├── .env.example                    # Environment variable template
└── .gitignore
```

## Quick Start

### 1. Backend (EX1)

```bash
cd backend
uv sync
mkdir -p data
uv run uvicorn app.main:app --reload
```

API at http://localhost:8000 — Docs at http://localhost:8000/docs

Optionally seed sample data (with the API running):

```bash
uv run python seed.py
```

Run tests:

```bash
uv run pytest -v                          # all backend tests (31)
uv run pytest tests/test_plants.py -v     # plant CRUD + auto-logging only
uv run pytest tests/test_care_events.py -v  # care events API only
uv run pytest tests/test_smoke.py -v      # health / docs smoke only
```

### 2. Frontend (EX2)

In a second terminal:

```bash
cd frontend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run plantpal_ui.py
```

> **Linux note:** Modern Debian/Ubuntu systems block `pip install` outside a virtual environment (PEP 668). The `python3 -m venv` step above creates a local `.venv` to work around this. On macOS/Windows you may be able to skip the venv, but using one is recommended regardless.

Dashboard at http://localhost:8501

Set `API_URL` if the backend runs on a different host:

```bash
API_URL=http://some-host:8000 streamlit run plantpal_ui.py
```

Run frontend tests (no running backend needed — uses mocks):

```bash
cd frontend
python3 -m pytest tests/ -v              # all frontend tests (8)
```

## Features

### Backend (EX1)

- Full CRUD for plants (`POST`, `GET`, `PUT`, `PATCH`, `DELETE`)
- **Care Events API** (`GET /care-events/`, `POST /care-events/`) — filterable by plant and event type
- **Auto-logging**: watering a plant or health degradation automatically creates timestamped care events
- SQLite persistence via SQLModel
- Health check endpoint (`/health`)
- CORS middleware for frontend integration
- 31 pytest tests (happy-path + error-path + validation + pagination + auto-logging + care events CRUD)
- Seed script with 6 sample plants

### Frontend (EX2)

- **Dashboard**: List all plants with health badges, light indicators, and watering status
- **Add / Edit / Delete**: Full CRUD through dialog forms
- **Water Now**: One-click watering that updates `last_watered` and logs a care event
- **Overdue Alerts**: Plants past their watering schedule are flagged with warnings
- **Care Log**: Full care history and insights page with:
  - Summary stats (weekly/monthly activity, care streak, most pampered plant)
  - Activity timeline with day grouping and filters by plant/event type
  - Per-plant drilldown with watering count, average interval, and full history
  - Add care notes (free-text observations attached to any plant)
- **Search & Filter**: Filter by name, location, health status, or light need
- **Export to JSON**: Download your plant collection as a JSON file
- Green/nature-themed dark UI

## AI Assistance

This project was built with the assistance of an AI coding agent (Claude / Cursor). The AI was used to:

- Generate the initial project scaffolding and boilerplate
- Implement CRUD service logic and route handlers
- Write pytest test cases
- Build the Streamlit dashboard layout and styling
- Draft documentation

All outputs were reviewed and tested locally. Backend tests (31 passing) and frontend tests (8 passing) verify correctness.
