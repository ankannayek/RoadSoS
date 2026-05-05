# RoadSoS Roadmap Status - Backend Production Pass

Verification date: 2026-05-04

| Roadmap category | Status | Verification point |
|---|---:|---|
| Auth + JWT | Complete | `/auth/register`, `/auth/login`, `core/security.py` |
| Protected admin bootstrap | Complete | `/auth/bootstrap-admin`, `ADMIN_BOOTSTRAP_TOKEN` |
| Encrypted medical/contact profile | Complete | `user_private_profiles`, `services/private_profile.py` |
| SOS trigger modes | Complete | manual, auto-detect, voice, silent, bystander |
| Atomic SOS handler | Complete | `/sos/trigger` writes incident + tier0 job in one DB transaction |
| No AI in SOS path | Complete | SOS/escalation import checks in tests |
| Rate limiter | Complete | Redis atomic increment path + in-memory dev fallback |
| PostGIS geo-matching | Complete | volunteer/service KNN search |
| Durable escalation ladder | Complete | tier0/tier1/tier2/tier3 scheduled jobs |
| Background worker concurrency | Complete | `TASK_WORKER_CONCURRENCY` |
| Provider notifications | Complete | FCM service account, Twilio SMS, optional WhatsApp |
| Notification/audit logs | Complete | `notification_logs`, `incident_responder_attempts` |
| Volunteer accept/decline | Complete | `/volunteers/incidents/{id}/respond` |
| WebSocket streams | Complete | incident and dashboard JWT streams |
| Helper Bot RAG | Complete | vector + keyword + RRF + citations |
| Gemini embeddings | Complete | `RAG_EMBEDDING_PROVIDER=gemini` |
| Groq/Gemini LLM | Complete | `RAG_LLM_PROVIDER=groq|gemini` |
| Local RAG fallback | Complete | hashing embeddings + extractive answer |
| Offline cache/SMS payload | Complete | geohash prefetch + `/sos/sms-fallback-payload` |
| Multi-source data pipeline | Complete | imports and report review |
| Judge dashboard | Complete | active incidents, metrics, timeline, WebSocket |
| Production readiness endpoint | Complete | `/health/ready` |
| Alembic migrations | Complete | `alembic/versions/20260504_0001_production_hardening.py` |

## Missing before real production

- Real FCM service-account JSON and Twilio credentials.
- Real Gemini/Groq keys if provider-backed Helper Bot answers are desired.
- Redis URL with `REQUIRE_REDIS_IN_PRODUCTION=true`.
- Field encryption key generated with `FieldEncryption.generate_key()` or an equivalent Fernet key generator.
- Staging migration run and RAG re-ingestion after vector dimension change to 768.
