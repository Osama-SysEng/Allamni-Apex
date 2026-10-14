# Allamni Architecture v3

```text
Flutter / Web
        |
   API Gateway
        |
+-------+-----------------------------+
| Auth | Learning | AI | Integration |
+-------+-----------------------------+
        |
 Domain Intelligence
        |
 Observe -> Profile -> Assess -> Reason
        -> Plan -> Teach -> Measure
        -> Adapt -> Act -> Verify -> Learn
        |
 +-------------------------------+
 | Agents: Student/Tutor/Content |
 | Assessment/Institution        |
 +-------------------------------+
        |
 Memory + Event Bus + Outbox
        |
 PostgreSQL / Redis / Qdrant / Odoo
```

### Design rules
1. LLM never owns authorization or critical numeric truth.
2. Every important mutation has an event/idempotency key.
3. Adaptive decisions are explainable through evidence.
4. Agent traces are observable and subject-scoped.
5. Integrations fail closed and retry safely.
6. Production providers implement existing interfaces; deterministic provider is explicit development fallback.
