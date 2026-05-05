# Verification Commands

Use Python 3.11 or 3.12 for the production runtime.

```bash
python -m compileall -q app
python -m pytest -q
alembic upgrade head
```

For integration verification, set:

```env
TEST_DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=rediss://...
```

Production readiness:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```
