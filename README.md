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
GET    /users/me
PATCH  /users/me
POST   /users/me/device-token
POST   /volunteers/me
PATCH  /volunteers/me
POST   /volunteers/toggle-availability
GET    /volunteers/nearby?lat=..&lng=..
POST   /sos/trigger
GET    /sos/incidents/{incident_id}
PATCH  /sos/incidents/{incident_id}/status
POST   /sos/incidents/{incident_id}/location
GET    /sos/offline-services?lat=..&lng=..
GET    /sos/sms-fallback-payload?lat=..&lng=..
WS     /sos/ws/{incident_id}?token=JWT
POST   /helper/query
POST   /feedback/
GET    /services/nearby?lat=..&lng=..
POST   /rag/ingest-default                 # admin
GET    /dashboard/incidents/active          # dispatcher/judge/admin
GET    /dashboard/metrics                   # dispatcher/judge/admin
GET    /dashboard/incidents/{id}/timeline   # dispatcher/judge/admin
WS     /dashboard/ws?token=JWT              # dispatcher/judge/admin
POST   /data-ingestion/services/import      # dispatcher/judge/admin
POST   /data-ingestion/services/report      # authenticated user report
PATCH  /data-ingestion/services/report/{id} # dispatcher/judge/admin review
```

## Example SOS request

```bash
curl -X POST http://localhost:8000/sos/trigger \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "description": "Car crash, one person unconscious and heavy bleeding",
    "lat": 13.0067,
    "lng": 80.2206,
    "impact_force": 9.2,
    "source": "auto_detect",
    "sensor_payload": {"airbag_deployed": true}
  }'
```

Expected result: `200 OK`, incident ID, priority, confidence, ETA. Escalation continues from the durable background queue.

## Seed the Helper Bot knowledge

After schema setup and login as an admin user:

```bash
curl -X POST http://localhost:8000/rag/ingest-default \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Production notes

- Set Redis and `REQUIRE_REDIS_IN_PRODUCTION=true` for multi-instance WebSocket fan-out and global cache/rate-limit behavior.
- Use provider credentials for FCM, WhatsApp Cloud API, and Twilio SMS before live dispatch testing.
- Use `RAG_EMBEDDING_PROVIDER=openai`, `RAG_LLM_ENABLED=true`, and `RAG_LLM_PROVIDER=openai` for real semantic embeddings and LLM generation.
- Keep hashing embeddings and extractive RAG as local/offline fallbacks.
- Use Alembic migrations for team workflow after applying this baseline schema.
- Promote at least one user to `admin` directly in the database before using admin-only endpoints.

See `docs/ROADMAP_STATUS_VERIFIED.md` for the verified category-by-category completion table.
