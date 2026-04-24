#!/usr/bin/env bash
# PlantPal EX3 end-to-end demo script.
# Walks a grader through: stack up -> seed -> list -> AI advice ->
# async refresh -> JWT login -> CSV export.  Safe to re-run.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_URL="${API_URL:-http://localhost:8000}"
USERNAME="${DEFAULT_EDITOR_USERNAME:-gardener}"
PASSWORD="${DEFAULT_EDITOR_PASSWORD:-plantpal}"

say() { printf "\n\033[1;32m>>> %s\033[0m\n" "$*"; }
compose() { docker compose -f "$ROOT/compose.yaml" "$@"; }

say "1/7  Starting the Compose stack (backend + frontend + ai_service + redis + worker)"
compose up -d --build

say "2/7  Waiting for the backend to report healthy"
for i in $(seq 1 30); do
  if curl -sf "$API_URL/health" >/dev/null; then
    echo "    backend is up"
    break
  fi
  sleep 2
done

say "3/7  Seeding sample plants (idempotent)"
compose exec -T backend uv run python seed.py || true

say "4/7  Listing plants from the API"
curl -s "$API_URL/plants/?limit=3" | python -m json.tool | head -40

say "5/7  Fetching AI advice for plant #1 (uses ai_service or the rule-based fallback)"
curl -s "$API_URL/plants/1/advice" | python -m json.tool

say "6/7  Logging in and exporting plants to CSV via the Typer CLI"
TOKEN=$(curl -s -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$USERNAME&password=$PASSWORD" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "    got JWT: ${TOKEN:0:24}..."
PLANTPAL_TOKEN="$TOKEN" python scripts/plantpal_cli.py export-csv --output plants_export.csv --api-url "$API_URL"

say "7/7  Running the async refresher (bounded concurrency + Redis idempotency)"
python scripts/refresh.py --limit 10 --api-url "$API_URL"

say "Done.  Streamlit UI: http://localhost:${FRONTEND_PORT:-8501}"
say "      Swagger docs: $API_URL/docs"
say "      Stop with:    docker compose -f compose.yaml down"
