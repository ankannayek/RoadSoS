# RoadSoS Backend

RoadSoS is the backend for a road-emergency app: users trigger SOS, nearby volunteers and official services are matched, dispatch updates stream live, and a separate Helper Bot gives grounded safety guidance.

The important rule is simple: **SOS is deterministic**. No LLM, Gemini, Groq, or RAG code runs in the emergency dispatch path. AI is only used in the Helper Bot, and even that has local fallbacks.

## What It Does

- JWT auth, user profiles, emergency contacts, medical details, and device tokens.
- Deterministic SOS triage for manual, auto-detect, voice, silent, and bystander modes.
- PostGIS matching for volunteers and emergency services.
- Durable tiered escalation through database-backed jobs.
- FCM push, Twilio SMS, optional WhatsApp, notification logs, and responder audit trails.
- Authenticated WebSocket streams for users and the judge/dispatcher dashboard.
- Feedback-based volunteer re-ranking.
- Offline service prefetch and SMS fallback payloads.
- Helper Bot RAG with Gemini embeddings, Groq/Gemini generation, and extractive fallback.

## Architecture Rules

- `/sos/trigger` must stay fast, auditable, and deterministic.
- Escalation jobs must be durable; one active incident must not block the worker.
- Production uses Redis for rate limits, cache, and WebSocket fan-out.
- Medical/contact fields are encrypted in production.
- Provider failures are logged; they are never silently treated as success.

## Local Setup

Use Python 3.12.

```bash
py -3.12 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

For Neon, keep `DATABASE_URL` in async form:

```env
DATABASE_URL=postgresql+asyncpg://...
```

Alembic converts it to the sync driver internally.

## Environment Groups

Core:

```env
ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://...
SECRET_KEY=change-this-in-production
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

Production safety:

```env
ENVIRONMENT=production
REDIS_URL=rediss://...
REQUIRE_REDIS_IN_PRODUCTION=true
FIELD_ENCRYPTION_KEYS=v1:<fernet-key>
TASK_QUEUE_BACKEND=database
```

Notifications:

```env
FCM_PROJECT_ID=
FCM_SERVICE_ACCOUNT_JSON=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
SMS_FALLBACK_NUMBER=112
```

Helper Bot providers:

```env
RAG_EMBEDDING_PROVIDER=gemini
RAG_LLM_ENABLED=true
RAG_LLM_PROVIDER=groq
GEMINI_API_KEY=
GROQ_API_KEY=
```

Empty Gemini/Groq keys are okay in local development; the backend falls back to hashing embeddings and extractive answers.

## Getting API Keys

- **Gemini:** go to [Google AI Studio](https://aistudio.google.com/app/apikey), create an API key, put it in `GEMINI_API_KEY`.
- **Groq:** go to [Groq Console](https://console.groq.com/keys), create an API key, put it in `GROQ_API_KEY`.
- **FCM:** create or open a Firebase project, enable Cloud Messaging, create a service account JSON, set `FCM_PROJECT_ID` and paste the JSON into `FCM_SERVICE_ACCOUNT_JSON` or base64-encode it.
- **Twilio:** create a Twilio account, buy/verify a sender number, then set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER`.
- **Field encryption:** generate a Fernet key and store it as `FIELD_ENCRYPTION_KEYS=v1:<key>`.

## Core Endpoints
# RoadSoS Backend — Verified Full Roadmap Package

FastAPI + Neon/PostGIS backend aligned with the uploaded architecture diagram: JWT auth, atomic SOS, deterministic triage, PostGIS KNN matching, durable escalation, provider notification hub, authenticated WebSockets, Judge Dashboard, feedback re-ranking, offline geohash cache, SMS fallback payloads, multi-source service ingestion, and Helper Bot-only hybrid RAG.

## Key architecture rules

- **SOS path is deterministic**: no AI/RAG/LLM in `/sos/trigger` or escalation.
- **Helper Bot path uses RAG only**: vector + keyword retrieval, RRF, grounded LLM adapter, extractive fallback.
- **Emergency work is durable**: SOS escalation jobs are persisted in `background_jobs` and processed by the lifespan worker.
- **Provider notifications are explicit**: FCM/WhatsApp/SMS are real HTTP adapters when credentials exist; otherwise attempts are logged as skipped/failed.
- **Dashboard/data ingestion are role-protected**: dispatcher/judge/admin for dashboard and imports; admin for RAG ingestion.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit DATABASE_URL, SECRET_KEY, Redis URL, CORS origins, and provider keys
psql "$DATABASE_URL_SYNC" -f database/schema.sql
uvicorn app.main:app --reload --port 8000
```

For Neon, use your async URL in `.env` for FastAPI (`postgresql+asyncpg://...`) and a normal `postgresql://...` URL in your shell for `psql`.

## Core endpoints

```text
POST   /auth/register
POST   /auth/login
POST   /auth/bootstrap-admin
GET    /users/me
PATCH  /users/me
POST   /users/me/device-token

POST   /volunteers/me
PATCH  /volunteers/me
POST   /volunteers/toggle-availability
GET    /volunteers/nearby
POST   /volunteers/incidents/{incident_id}/respond

POST   /sos/trigger
GET    /sos/incidents/{incident_id}
PATCH  /sos/incidents/{incident_id}/status
POST   /sos/incidents/{incident_id}/location
GET    /sos/offline-services
GET    /sos/sms-fallback-payload
WS     /sos/ws/{incident_id}?token=JWT

POST   /helper/query
POST   /feedback/
GET    /services/nearby

POST   /rag/ingest-default
GET    /dashboard/incidents/active
GET    /dashboard/metrics
GET    /dashboard/incidents/{id}/timeline
WS     /dashboard/ws?token=JWT

POST   /data-ingestion/services/import
POST   /data-ingestion/services/report
PATCH  /data-ingestion/services/report/{id}

GET    /health/live
GET    /health/ready
```

## Testing

```bash
py -3.12 -m compileall -q app alembic tests
py -3.12 -m pytest -q -p no:cacheprovider
py -3.12 -c "import app.main; print('import_ok')"
```

Database integration tests stay skipped unless `TEST_DATABASE_URL` points to a Postgres database with PostGIS, pgcrypto, and pgvector.

## Production Checklist

- Rotate any secret that was ever shared outside a secret manager.
- Run `alembic upgrade head` on staging first.
- Set Redis and `REQUIRE_REDIS_IN_PRODUCTION=true`.
- Set `FIELD_ENCRYPTION_KEYS` before storing real medical data.
- Configure FCM and Twilio before live dispatch testing.
- Re-ingest RAG knowledge after changing embedding provider or vector dimension.
- Hit `/health/ready` and fix every failed check before going live.
