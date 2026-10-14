# Structured Logging — Allamni-Apex

Shared unit: `backend/shared/logging_utils.py` (stdlib only, no new dependencies).
Copied from the canonical template (`C:\pgload\logging_template.py`) with the
default adapted to `SERVICE_NAME=allamni-api`.

## Schema (one JSON object per line)

`timestamp` (UTC ISO-8601 ms) + `level` + `service` + `env` + `version`
+ `request_id` + `event` + `message`. Optional merged `fields` are redacted
(password / token / secret / apikey / authorization / cookie / national_id …).

## Configuration (`.env.example`)

| Variable       | Default        | Notes                                            |
|----------------|----------------|--------------------------------------------------|
| `SERVICE_NAME` | `allamni-api`  | Override per service (e.g. `allamni-gateway`)    |
| `LOG_LEVEL`    | `info`         | `debug` when `ENVIRONMENT` is not `production`   |
| `GIT_SHA`      | `dev`          | Emitted as `version`; set in CI/CD               |
| `ENVIRONMENT`  | `development`  | Emitted as `env`                                 |

## Wired so far

- `backend/api_gateway/app/main.py`: `get_logger("gateway")` + `access_log_middleware`
  (propagates incoming `X-Request-ID` or generates one via `new_request_id()`,
  sets `request_id_ctx`, logs one `access: METHOD path -> status in Xms` line per
  request with `http.method/http.path/http.status/duration_ms` fields, echoes
  `X-Request-ID` on the response; failures logged via `logger.exception`).
- `print` in runtime code replaced with structured/std logger calls:
  `services/ai-service/app/main.py` (3), `services/ai-service/app/providers.py` (1),
  `shared/self_learning.py` (1), `shared/real_time_features.py` (2),
  `shared/powerful_ai_chatbot.py` (1), `shared/arabic_nlp.py` (1).
  `print` statements remaining under `backend/tests/` are intentional (test output).

## Per-service logging modules

Verified 2026-10-14: the five services (`auth`, `learning`, `ai`, `integration`,
`institution`) have **no dedicated logging modules** — no `logging_utils`,
`logger.py`, or `get_logger` of their own — so nothing was kept/merged and
nothing was broken. Migration path: each service sets its own `SERVICE_NAME`
and replaces `logging.getLogger(...)` / remaining prints with
`from shared.logging_utils import get_logger` (same pattern as the gateway).

## Usage

```python
from shared.logging_utils import get_logger, new_request_id, request_id_ctx

logger = get_logger(__name__)
request_id_ctx.set(new_request_id())
logger.info("startup: service ready", extra={"fields": {"port": 8001}})
```

Never log secrets; the formatter redacts risky keys automatically.
