#!/usr/bin/env bash
# PlantPal EX3 – end-to-end demo script.
#
# Steps:
#   1  Bring the Compose stack up
#   2  Wait for the backend to be healthy
#   3  Seed sample plants (idempotent)
#   4  List plants via REST
#   5  Fetch AI advice for plant #1
#   6  Log in and export plants to CSV via the Typer CLI
#   7  Run the async health refresher
#
# Re-run safe.  Requires: docker, docker compose, python3, curl.

set -euo pipefail

# ── paths ────────────────────────────────────────────────────────────────────
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$ROOT/scripts"
VENV_DIR="$SCRIPTS_DIR/.venv"
cd "$ROOT"

# ── config ───────────────────────────────────────────────────────────────────
API_URL="${API_URL:-http://localhost:8000}"
USERNAME="${DEFAULT_EDITOR_USERNAME:-gardener}"
PASSWORD="${DEFAULT_EDITOR_PASSWORD:-plantpal}"

# ── helpers ──────────────────────────────────────────────────────────────────
say()     { printf "\n\033[1;32m>>> %s\033[0m\n" "$*"; }
compose() { docker compose -f "$ROOT/compose.yaml" "$@"; }

# Bootstrap a lightweight venv for the host-side Typer CLI (plantpal_cli.py).
# plantpal_cli.py is a pure HTTP client — it only needs httpx + typer.
# Only created once; subsequent runs skip the install.
setup_venv() {
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "    creating venv at scripts/.venv …"
    python3 -m venv "$VENV_DIR"
  fi
  if ! "$VENV_DIR/bin/python" -c "import httpx, typer" 2>/dev/null; then
    echo "    installing httpx typer into venv …"
    "$VENV_DIR/bin/pip" install --quiet httpx typer
  fi
}

# ── 1/7 ──────────────────────────────────────────────────────────────────────
say "1/7  Starting the Compose stack (backend · frontend · ai_service · redis · worker)"
compose up -d --build

# ── 2/7 ──────────────────────────────────────────────────────────────────────
say "2/7  Waiting for the backend to be healthy (up to 60 s)"
for i in $(seq 1 30); do
  if curl -sf "$API_URL/health" >/dev/null; then
    echo "    backend is up (attempt $i)"
    break
  fi
  sleep 2
done

# ── 3/7 ──────────────────────────────────────────────────────────────────────
say "3/7  Seeding sample plants (idempotent)"
compose exec -T backend uv run python seed.py || true

# ── 4/7 ──────────────────────────────────────────────────────────────────────
say "4/7  Listing plants from the REST API (first 3)"
curl -s "$API_URL/plants/?limit=3" | python3 -m json.tool | head -40

# ── 5/7 ──────────────────────────────────────────────────────────────────────
say "5/7  Fetching AI advice for plant #1 (ai_service or rule-based fallback)"
curl -s "$API_URL/plants/1/advice" | python3 -m json.tool

# ── 6/7 ──────────────────────────────────────────────────────────────────────
say "6/7  Logging in and exporting plants to CSV via the Typer CLI"

setup_venv

TOKEN=$(curl -s -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$USERNAME&password=$PASSWORD" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
echo "    got JWT: ${TOKEN:0:30}…"

PLANTPAL_TOKEN="$TOKEN" \
  "$VENV_DIR/bin/python" "$SCRIPTS_DIR/plantpal_cli.py" \
    export-csv --output plants_export.csv --api-url "$API_URL"

echo "    exported → plants_export.csv"

# ── 7/7 ──────────────────────────────────────────────────────────────────────
# The worker service runs refresh.py inside the backend image on the internal
# Docker network, where the backend is reachable as http://backend:8000.
# We use `compose run --rm` to fire a one-shot run with the same setup.
say "7/7  Running the async health refresher (bounded concurrency + Redis idempotency)"
compose run --rm \
  -e REDIS_URL=redis://redis:6379/0 \
  -e API_URL=http://backend:8000 \
  worker \
  uv run python /workspace/scripts/refresh.py --limit 10 --api-url http://backend:8000

# ── done ─────────────────────────────────────────────────────────────────────
say "Done."
echo "    Streamlit UI : http://localhost:${FRONTEND_PORT:-8501}"
echo "    Swagger docs : $API_URL/docs"
echo "    Stop stack   : docker compose -f compose.yaml down"
