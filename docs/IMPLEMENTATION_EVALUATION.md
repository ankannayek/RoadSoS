# RoadSoS Backend Evaluation - Production Hardening Pass

Verification date: 2026-05-04

## Implemented hardening

1. **Provider-neutral Helper Bot** - OpenAI-specific settings were removed from app code. Gemini embeddings and Groq/Gemini grounded generation are supported, with hashing/extractive local fallbacks when keys are absent.
2. **Deterministic SOS isolation** - SOS trigger and escalation do not import or call RAG, Gemini, Groq, or LLM code.
3. **Durable discrete escalation** - Tier 0/1/2/3 escalation now uses separate scheduled `background_jobs` instead of long sleeps inside one worker job.
4. **Queue concurrency and dedupe** - The DB queue supports configurable worker concurrency and active-job dedupe keys.
5. **Production Redis posture** - Redis can be required in production; cache, rate limits, and event bus expose readiness pings.
6. **Atomic rate limiting** - Redis-backed rate limiting uses a Lua increment+expire operation and stable SHA-256 client identifiers.
7. **FCM service-account push** - Push delivery mints OAuth tokens from `FCM_SERVICE_ACCOUNT_JSON`; static FCM access tokens are no longer required.
8. **Twilio SMS path** - Twilio remains the required SMS provider for production readiness.
9. **Encrypted medical profile storage** - Medical/contact fields are persisted in `user_private_profiles`; production requires `FIELD_ENCRYPTION_KEYS`.
10. **Admin bootstrap API** - First admin can be promoted through a setup-token endpoint, then disabled.
11. **Responder flow** - Volunteers can accept/decline incidents; attempts are audited and broadcast to incident/dashboard streams.
12. **Readiness checks** - `/health/live` and `/health/ready` report DB, Redis/cache/event bus, queue, provider, encryption, and RAG readiness.
13. **Alembic path** - Alembic config and a baseline hardening migration are included.

## Production env still required

The backend boots locally without Gemini/Groq keys and falls back to local RAG behavior. Before live production, configure:

```env
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=rediss://...
SECRET_KEY=...
REQUIRE_REDIS_IN_PRODUCTION=true
FIELD_ENCRYPTION_KEYS=key-id:fernet-key
FCM_PROJECT_ID=...
FCM_SERVICE_ACCOUNT_JSON=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=...
RAG_EMBEDDING_PROVIDER=gemini
RAG_LLM_PROVIDER=groq
GEMINI_API_KEY=...
GROQ_API_KEY=...
```

## Remaining operational work

- Rotate any real secrets that were ever stored in a local `.env` shared outside the deployment secret manager.
- Run `alembic upgrade head` on a staging Neon database and re-ingest RAG chunks because the vector dimension is now 768.
- Run integration tests with `TEST_DATABASE_URL` against PostGIS/pgvector and Redis before live dispatch.
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
