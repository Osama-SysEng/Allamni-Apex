# Allamni – علّمني — v3.0

AI-native Adaptive Education Operating System.

## Vision
Allamni serves students, children, adults, teachers and institutions. It adapts assessment, explanation, content and learning paths to the individual instead of giving everyone the same exam or teaching method.

## Intelligence loop
`Observe -> Profile -> Assess -> Reason -> Plan -> Teach -> Measure -> Adapt -> Act -> Verify -> Learn`

## Student intelligence
- Digital learning profile
- Cognitive snapshot
- Mastery + confidence + gap + stability
- Risk scoring
- Adaptive difficulty control
- Next-best-action
- Dynamic roadmap
- Learning memory

## Teacher intelligence
Foundation supports teacher-aware profiles and institution-level analytics. Teacher-specific UI/flows can consume same intelligence contracts.

## Agent system
- Student Agent
- Assessment Agent
- Tutor Agent
- Content Agent
- Institution Agent
- Orchestrator with trace IDs

## Content system
Lesson blueprints can combine:
- Mind maps
- Interactive games
- Visual explanations
- Video/image resources
- Real-life questions
- Micro assessments

External media must be validated before publication.

## Enterprise
- RBAC
- owner-scoped student access
- event bus
- idempotency
- outbox pattern
- Odoo integration boundary
- audit-friendly agent traces
- metrics
- Docker
- CI

## Run
```bash
cp .env.example .env
docker compose up --build
```

API: http://localhost:8000
Swagger: http://localhost:8000/docs

## Tests
```bash
cd backend
python -m pytest -q
```

## Important
Real LLM, Odoo, production database repositories, object storage and deployment credentials are environment-specific. Development fallback is deterministic and explicitly labeled; no fake integration is presented as production-live.

## What's New (Oct 2026)
- Live PostgreSQL (15 tables) + `.env.example`
- 55 tests collected, 0 collection errors
- Interactive 3D showcase: open `web-3d/index.html` (Three.js, animated, mouse-reactive)
- Structured JSON logging + X-Request-ID tracing (see docs/LOGGING.md)
