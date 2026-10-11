# Scaling — Allamni-Apex backend

## Workers
- All service Dockerfiles (`backend/api_gateway`, `backend/services/*`,
  root `Dockerfile`, `infrastructure/docker/Dockerfile.{gateway,service}`)
  run uvicorn with `--workers 2`.
- Services are stateless FastAPI behind the gateway; scale with replicas.
- NOTE: `backend/shared/store.py` is an **in-memory** store. Multi-worker /
  multi-replica deployments do NOT share sessions, codes, rate-limit counters
  or outbox state. For production, replace with Redis/Postgres before scaling
  out; until then prefer `--workers 1` + sticky sessions if correctness of
  shared state matters more than throughput.

## Rate limiting
- Gateway (`backend/api_gateway/app/main.py`): in-memory per-IP sliding
  window, default **300 req/min** (`GATEWAY_RATE_LIMIT` env), `/health`
  exempt, 429 on excess.
- Auth login additionally gated by `advanced_security.check_rate_limit`
  (service-level, in-memory store).
- Per-worker memory only: N workers ≈ N× budget. Use Redis for a global
  budget.

## Pagination (default 50 / max 500)
- Institution codes/students/teachers/invoices: `limit` clamped to
  `[1, 500]`, `offset >= 0`; list endpoints return `total/limit/offset`.
- Auth `/auth/sessions`, `/auth/security-events`: new optional
  `limit/offset` (defaults 50/0) — old calls unaffected.
- AI `/notifications/{user_id}`: new optional `limit/offset`, sliced
  server-side.
- Integration `/odoo/sync/history`: existing `limit` now clamped to 500 +
  new `offset`.
- No endpoint signature was broken: new params are optional with defaults.

## Remaining capacity limits (honest)
- In-memory store is the #1 ceiling: no cross-worker consistency, data loss
  on restart, unbounded dict growth (sessions, events, outbox).
- No caching layer; dashboard/analytics endpoints recompute per request.
- Gateway proxy uses a fresh `httpx.AsyncClient` per request — connection
  churn under load; use a shared client + pool in production.
