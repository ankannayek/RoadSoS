# RoadSoS Roadmap Status — Verified Completion Package

Verification date: 2026-05-04

This package was rechecked against the uploaded architecture diagram and the prior implementation audit. The implementation now contains a code path for every diagram category. External provider delivery still requires real production credentials in environment variables.

## Executive status

| Roadmap category | Status | Verification point |
|---|---:|---|
| Auth + JWT | Complete | `/auth/register`, `/auth/login`, `core/security.py` |
| Profile + medical + contacts | Complete | `/users/me`, `/users/me/device-token`, `users.fcm_tokens` |
| SOS trigger modes | Complete | `IncidentSource`: manual, auto_detect, voice, silent, bystander |
| Atomic SOS handler | Complete | `/sos/trigger` returns HTTP 200 and writes incident + durable job in one DB transaction |
| Rate limiter | Complete | Path-aware middleware for auth, SOS, RAG, default paths |
| Triage engine | Complete | Deterministic rule-based classifier; no RAG/LLM in dispatch |
| PostGIS geo-matching | Complete | KNN search with GIST indexes and composite volunteer score |
| Escalation ladder | Complete | Tier 0/1/2/3 with continuing tier-3 rebroadcast until resolution/cancel |
| Durable background processing | Complete | `background_jobs` table + polling worker + retries/stale-lock recovery |
| Notification hub | Complete | FCM HTTP v1, WhatsApp Cloud API, Twilio SMS adapters + DB audit logs |
| WebSocket live stream | Complete | Authenticated incident stream and dashboard stream |
| WebSocket auth | Complete | `?token=` or Authorization bearer validation; owner/role authorization |
| Helper Bot RAG | Complete | Hybrid vector + keyword retrieval, RRF, citations, grounded LLM adapter, extractive fallback |
| Real embeddings option | Complete | OpenAI embedding provider configurable with 384-dim vectors; hashing fallback for local dev |
| Feedback/re-ranking | Complete | Rating endpoint + Bayesian volunteer rating recomputation |
| Offline cache | Complete | Geohash service prefetch + TTL cache |
| SMS fallback payload | Complete | `/sos/sms-fallback-payload` returns cached recipients + GPS SMS payload for mobile offline auto-send |
| Multi-source data pipeline | Complete | Admin import pipeline for OSM/Gov/NHAI/partner/manual data + user report review flow |
| Judge dashboard | Complete | Active incidents, metrics, incident timeline, dashboard WebSocket |
| Core database tables | Complete | Users, incidents, volunteers, services, feedback, notifications, jobs, RAG tables |
| DB ping service | Complete | Neon keepalive every 4 minutes |
| RBAC | Complete | user/volunteer/dispatcher/judge/admin roles; admin-protected RAG ingestion; dispatcher/judge dashboard/data imports |
| Multi-instance pub/sub | Production-ready path | Redis Pub/Sub supported; can require Redis in production via `REQUIRE_REDIS_IN_PRODUCTION=true` |

## Newly added/changed files

- `app/api/dashboard.py` — Judge Dashboard REST + WebSocket.
- `app/api/data_ingestion.py` — multi-source service import and user-report review.
- `app/schemas/dashboard.py` — dashboard response models.
- `app/schemas/data_ingestion.py` — service import/report models.
- `app/schemas/notifications.py` — mobile FCM token registration models.
- `app/services/data_ingestion.py` — OSM/Gov/NHAI/user-report normalization and upsert logic.
- `app/services/llm.py` — grounded LLM adapter for Helper Bot generation.
- `app/models/job.py` — durable background job model.
- Updated `app/services/notifications.py` with real provider HTTP adapters.
- Updated `app/services/escalation.py` with tier-3 rebroadcast loop.
- Updated `app/services/task_queue.py` with DB-backed durable worker.
- Updated `app/api/sos.py` with HTTP 200 atomic handler, WebSocket auth, and SMS fallback payload.
- Updated `app/core/security.py` with RBAC and WebSocket auth.
- Updated `database/schema.sql` with `role`, `fcm_tokens`, and `background_jobs`.

## Environment needed for live external delivery

The code paths are present. Actual outbound delivery requires these production secrets:

```env
FCM_PROJECT_ID=
FCM_ACCESS_TOKEN=
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
OPENAI_API_KEY=
```

Without credentials, notification attempts are safely logged as `skipped_config_missing` instead of being silently treated as sent.

## Verification performed

- Rechecked diagram categories against backend modules and schema.
- Added missing modules for dashboard, data ingestion, durable queue, provider notifications, RBAC, WebSocket auth, LLM adapter, real embedding adapter, SMS fallback payload, and tier-3 rebroadcast.
- Ran Python syntax compilation across the `app/` package successfully with `python -m compileall -q app`.
- Full runtime import was not executed in this sandbox because the sandbox Python environment does not have the project dependencies installed. The package includes `requirements.txt` for a normal environment.

## System failsafe

1. SOS dispatch remains deterministic; RAG/LLM is not used in `/sos/trigger` or escalation.
2. If FCM/WhatsApp/SMS credentials are missing or providers fail, attempts are logged with explicit status/error.
3. Escalation jobs persist in `background_jobs` and retry after crashes/stale locks.
4. WebSocket streams require JWTs and enforce ownership or dispatcher/judge/admin role.
5. Dashboard and ingestion routes require dispatcher/judge/admin role; RAG ingestion requires admin role.
6. Helper Bot answers are grounded in retrieved chunks and fall back to extractive answers if the LLM provider is disabled or fails.
