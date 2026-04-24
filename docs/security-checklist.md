# PlantPal Security Checklist

Baseline controls from Session 11, audited against the OWASP API Top 3.

## Authentication & authorization

- [x] Password hashing with `passlib` + `bcrypt` — no plaintext storage
      ([`backend/app/security.py`](../backend/app/security.py))
- [x] `/token` endpoint issues short-lived JWTs (30 min by default) with
      `exp`, `iat`, `iss`, `aud`, and `roles` claims
- [x] `require_role("editor")` protects every write route on `/plants/`
- [x] Read routes stay anonymous so the EX2 Streamlit UI needs no login

## Input validation

- [x] Every request body is a Pydantic model — FastAPI returns 422 on
      bad input automatically
- [x] `PlantUpdate` uses `exclude_unset` so unknown/extra fields do not
      corrupt state
- [x] CSV import (`scripts/plantpal_cli.py`) rejects rows missing
      `name` or `species`

## Secrets & configuration

- [x] `.env` is gitignored; only `.env.example` ships in the repo
- [x] `JWT_SECRET`, `GOOGLE_API_KEY`, and passwords come from env vars
- [x] Docker Compose passes secrets through `environment:` so they
      never end up in the built image

## Rate limiting & abuse protection

- [x] Redis-backed fixed-window limiter (60 req/min per IP/path by
      default) with `X-RateLimit-*` headers
- [x] Idempotency keys on the async refresher prevent duplicate work
      across retries or restarts

## Tests

- [x] 401 without a token
- [x] 403 with the wrong role (viewer vs editor)
- [x] 401 with an expired token
- [x] 401 with a malformed token
- [x] Login success returns a valid access token

## Rotation procedure

1. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
2. Replace `JWT_SECRET` in the target `.env`
3. `docker compose restart backend`
4. Notify clients — all in-flight tokens are invalidated

## Scanning

Run before each release:

```bash
# trufflehog: requires the CLI on PATH
trufflehog filesystem --exclude-paths .gitignore . || true
```
