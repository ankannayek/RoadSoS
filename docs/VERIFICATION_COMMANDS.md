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
```text
$ python -m compileall -q app
compile_ok

$ grep -R "@router" -n app/api | sort
app/api/auth.py:16:@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
app/api/auth.py:44:@router.post("/login", response_model=TokenResponse)
app/api/dashboard.py:153:@router.get("/incidents/{incident_id}/timeline", response_model=list[IncidentTimelineEvent])
app/api/dashboard.py:176:@router.websocket("/ws")
app/api/dashboard.py:18:@router.get("/incidents/active", response_model=list[DashboardIncident])
app/api/dashboard.py:54:@router.get("/metrics", response_model=DashboardMetrics)
app/api/data_ingestion.py:19:@router.post("/services/import", response_model=ServiceImportResponse)
app/api/data_ingestion.py:36:@router.post("/services/report", response_model=ServiceReportOut)
app/api/data_ingestion.py:45:@router.patch("/services/report/{report_id}", response_model=ServiceReportOut)
app/api/feedback.py:18:@router.post("/", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
app/api/helper.py:15:@router.post("/query", response_model=HelperAnswer)
app/api/rag_admin.py:16:@router.post("/ingest-default")
app/api/services.py:14:@router.get("/nearby")
app/api/sos.py:100:@router.get("/offline-services", response_model=OfflineServicesResponse)
app/api/sos.py:105:@router.get("/sms-fallback-payload", response_model=SMSFallbackPayload)
app/api/sos.py:124:@router.websocket("/ws/{incident_id}")
app/api/sos.py:32:@router.post("/trigger", response_model=SOSResponse, status_code=status.HTTP_200_OK)
app/api/sos.py:72:@router.get("/incidents/{incident_id}", response_model=IncidentOut)
app/api/sos.py:77:@router.patch("/incidents/{incident_id}/status", response_model=IncidentOut)
app/api/sos.py:90:@router.post("/incidents/{incident_id}/location")
app/api/user.py:17:@router.get("/me", response_model=UserOut)
app/api/user.py:22:@router.patch("/me", response_model=UserOut)
app/api/user.py:36:@router.post("/me/device-token", response_model=DeviceTokenResponse)
app/api/volunteer.py:17:@router.post("/me", response_model=VolunteerOut, status_code=status.HTTP_201_CREATED)
app/api/volunteer.py:36:@router.patch("/me", response_model=VolunteerOut)
app/api/volunteer.py:54:@router.post("/toggle-availability")
app/api/volunteer.py:65:@router.get("/nearby")
```
