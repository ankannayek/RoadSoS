# RoadSoS Backend Evaluation — Current Package

This evaluation reflects the verified package after rechecking against the architecture diagram and the prior audit.

## What is complete now

1. **Judge Dashboard** — implemented in `app/api/dashboard.py` with active incidents, metrics, incident timeline, and dashboard WebSocket.
2. **Provider Notification Hub** — implemented in `app/services/notifications.py` with FCM HTTP v1, WhatsApp Cloud API, and Twilio SMS adapters, plus `notification_logs` audit records.
3. **SMS fallback payload** — implemented in `/sos/sms-fallback-payload` for Flutter to cache and auto-send GPS/location payloads when internet is unavailable.
4. **Multi-source data pipeline** — implemented in `app/services/data_ingestion.py` and `app/api/data_ingestion.py` for OSM/Gov/NHAI/partner/manual imports and user reports.
5. **Durable escalation jobs** — implemented in `background_jobs` and `app/services/task_queue.py` so escalations are recoverable after process restarts.
6. **WebSocket authentication** — implemented for incident and dashboard streams with JWT query/header validation and ownership/role checks.
7. **Role-based access control** — user roles now support `user`, `volunteer`, `dispatcher`, `judge`, and `admin`.
8. **Tier-3 rebroadcast** — escalation now continues tier-3 volunteer/service/dashboard rebroadcasts until the incident is resolved/cancelled.
9. **RAG generation adapter** — Helper Bot has a grounded LLM adapter with an extractive fallback.
10. **Real embeddings option** — OpenAI embeddings can be enabled while deterministic hashing remains the local fallback.
11. **Atomic SOS response** — `/sos/trigger` now returns `200 OK` and queues durable escalation work in the same transaction.

## Boundaries that require production credentials/configuration

- FCM, WhatsApp, and SMS delivery require provider credentials in environment variables.
- OpenAI embeddings and LLM generation require `OPENAI_API_KEY` and relevant RAG settings.
- Multi-instance WebSocket fan-out should use Redis; set `REQUIRE_REDIS_IN_PRODUCTION=true` to enforce this in production.
- An initial admin user must be promoted in the database before admin-only endpoints can be used.

## Verification checklist

- `python -m compileall -q app` completed successfully.
- Route map includes dashboard, data-ingestion, SMS fallback, device-token registration, and authenticated WebSocket endpoints.
- Schema includes `users.role`, `users.fcm_tokens`, `background_jobs`, notification logs, RAG tables, PostGIS locations, and GIST/vector/text indexes.
- SOS code path imports no RAG/LLM module and uses deterministic triage + durable queue only.

## Recommended production hardening

- Move from raw SQL schema to Alembic migrations.
- Add provider delivery callbacks/webhooks to update notification status after carrier delivery.
- Add CI integration tests with Postgres + PostGIS + pgvector.
- Encrypt sensitive medical fields at rest if required by your compliance scope.
- Add OpenTelemetry traces and structured JSON logs.
