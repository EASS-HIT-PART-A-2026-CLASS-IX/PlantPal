# PlantPal — EX3 Notes

Course deliverables for EX3 (Full-Stack Microservices).

---

## 1. Services overview

Five cooperating services wired in [`compose.yaml`](../compose.yaml):

| Service | Role | Port |
|---------|------|------|
| `redis` | Cache, rate-limit counters, idempotency store | 6379 |
| `backend` | FastAPI + SQLModel/SQLite — main REST API | 8000 |
| `ai_service` | FastAPI + Pydantic AI plant care advisor | 8001 |
| `frontend` | Streamlit dashboard | 8501 |
| `worker` | Long-running async health-refresh loop | — |

Start everything with one command:

```bash
sudo docker compose -f compose.yaml up --build
```

Healthchecks gate `depends_on`:

- `backend` waits for `redis` and `ai_service` to be healthy
- `frontend` waits for `backend` to be healthy
- `worker` waits for `backend` and `redis` to be healthy

---

## 2. 4th microservice — AI plant advisor

`ai_service/` is a standalone FastAPI service with a single
`POST /advice` endpoint. The backend proxies it through
`GET /plants/{id}/advice`.

### Rule-based mode (no config needed)

Works immediately with zero setup. The service uses the plant's
`health_status`, `light_need`, `water_frequency_hours`, and
`location` to produce deterministic care tips.

```bash
curl http://localhost:8000/plants/1/advice
```

```json
{
  "plant_id": 1,
  "plant_name": "Monstera",
  "summary": "Care tips for Monstera (Monstera deliciosa).",
  "tips": ["Keep following the current schedule — looking good!", ...],
  "source": "rule-based"
}
```

### Gemini LLM mode (requires Google AI Studio key)

When `GOOGLE_API_KEY` and `GOOGLE_GEMINI_MODEL` are set, the
service uses Pydantic AI to call the Gemini API for plant-specific
generated advice.

1. **Get a free API key:** https://aistudio.google.com/ →
   **Get API key** → **Create API key**

2. **Set in `.env`:**

   ```ini
   GOOGLE_API_KEY=AIza...your-key...
   GOOGLE_GEMINI_MODEL=gemini-1.5-flash
   ```

3. **Rebuild the AI service:**

   ```bash
   sudo docker compose -f compose.yaml up --build ai_service
   ```

4. **Verify:**

   ```bash
   curl http://localhost:8000/plants/1/advice | python3 -m json.tool
   ```

   Look for `"source": "gemini"` in the response — that confirms
   the LLM path is active.

5. **In the Streamlit dashboard**, click **🤖** on any plant card
   to see the advice panel.

> If the AI service is unreachable or `GOOGLE_API_KEY` is not set,
> the backend silently falls back to rule-based mode. The stack
> always works end-to-end.

---

## 3. Async refresh — Session 09

[`scripts/refresh.py`](../scripts/refresh.py) implements
`PlantHealthRefresher`:

- `asyncio.Semaphore(refresh_max_concurrency)` caps in-flight HTTP calls
- `tenacity.AsyncRetrying` retries transient `httpx.HTTPError`s with
  exponential jitter (initial 0.5 s, max 5 s, stop after 3 attempts)
- `idempotency_check_and_set` uses Redis `SET NX` with a daily key
  (`plant-health:{plant_id}:{YYYY-MM-DD}`) so re-runs within the same
  day short-circuit instead of re-hammering the backend
- Every request carries `X-Trace-Id` and `Idempotency-Key` headers

### How to run

```bash
# Outside Docker (from repo root)
backend/.venv/bin/python scripts/refresh.py --limit 10

# Inside Docker worker
sudo docker compose -f compose.yaml exec worker \
  uv run python /workspace/scripts/refresh.py --limit 50 \
  --api-url http://backend:8000
```

### Test coverage

[`scripts/tests/test_refresh.py`](../scripts/tests/test_refresh.py)
uses `pytest.mark.anyio` with `httpx.ASGITransport` to drive a minimal
FastAPI app in-process — no running server needed.

### Trace excerpt

Fresh run (all plants processed):

```
INFO [plantpal.refresh] starting trace_id=plantpal-refresh-8f1c4a2e jobs=8
INFO [plantpal.refresh] refreshed plant_id=1 idempotency_key=plant-health:1:2026-04-24
INFO [plantpal.refresh] refreshed plant_id=2 idempotency_key=plant-health:2:2026-04-24
...
INFO [plantpal.refresh] done summary={'processed': 8, 'skipped_duplicate': 0, 'total': 8}
```

Re-run within the same day (idempotency kicks in):

```
INFO [plantpal.refresh] done summary={'processed': 0, 'skipped_duplicate': 8, 'total': 8}
```

---

## 4. Security baseline — Session 11

- `passlib` + `bcrypt` hash every password; raw passwords never hit
  disk or logs
- `POST /token` issues an HS256 JWT with `exp`, `iat`, `iss`, `aud`,
  and `roles` claims (30-minute default lifetime)
- `require_role("editor")` gates every write on `/plants/`
  (POST / PUT / PATCH / DELETE) — read routes stay public
- Tests in [`backend/tests/test_security.py`](../backend/tests/test_security.py)
  cover 401 (no token), 403 (wrong role), 401 (expired token), 401 (malformed)

### Default dev credentials

| Username | Password | Role |
|----------|----------|------|
| `gardener` | `plantpal` | editor |
| `viewer` | `viewer` | viewer |

Change via `DEFAULT_EDITOR_USERNAME` / `DEFAULT_EDITOR_PASSWORD` in `.env`.

### JWT rotation steps

1. Generate a strong new secret:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

2. Replace `JWT_SECRET` in `.env`

3. Restart the backend:

   ```bash
   sudo docker compose -f compose.yaml restart backend
   ```

4. All outstanding tokens are immediately invalidated — clients will
   receive 401 and must re-login.

5. Audit: nothing in the codebase hardcodes secrets; all sensitive
   values come exclusively from environment variables.

---

## 5. Redis-backed reliability — Session 10

- `GET /plants/` responses cached for 60 seconds; any write
  (`POST`/`PUT`/`PATCH`/`DELETE`) calls `invalidate_plants_cache()`
  using `scan_iter` to delete all parametrized cache keys
- Fixed-window rate limiter (60 req/min per IP per path by default)
  emits `X-RateLimit-Limit` and `X-RateLimit-Remaining` response headers
- Refresh idempotency via Redis `SET NX` daily keys
- All Redis helpers fail open — if Redis is unreachable the API keeps
  serving (no caching, no limiting, no idempotency — but no outage)

---

## 6. Enhancement — CSV export/import

Typer CLI commands for backing up and restoring the plant catalog:

```bash
# Export all plants to plants.csv
python scripts/plantpal_cli.py export-csv --output plants.csv

# Import from CSV into a fresh instance (requires editor token)
PLANTPAL_TOKEN=$(python scripts/plantpal_cli.py login \
  --username gardener --password plantpal)
PLANTPAL_TOKEN=$PLANTPAL_TOKEN python scripts/plantpal_cli.py \
  import-csv plants.csv
```

Covered by [`scripts/tests/test_cli.py`](../scripts/tests/test_cli.py).

---

## 7. Demo

Run the full end-to-end walkthrough:

```bash
./scripts/demo.sh
```

The script: seeds data → lists plants → logs in → exports CSV → fetches
AI advice → runs the async refresher → confirms idempotency.

Or step through it manually — see [`docs/runbooks/compose.md`](runbooks/compose.md).
