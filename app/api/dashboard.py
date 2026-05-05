from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import authenticate_websocket_user, require_dispatcher
from app.db.session import AsyncSessionLocal, get_db
from app.models.user import User
from app.schemas.dashboard import DashboardIncident, DashboardMetrics, IncidentTimelineEvent
from app.services.websocket_manager import websocket_manager

router = APIRouter()


@router.get("/incidents/active", response_model=list[DashboardIncident])
async def active_incidents(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_dispatcher),
):
    result = await db.execute(
        text(
            """
            SELECT i.id, i.user_id, i.priority::text AS priority, i.status::text AS status,
                   i.source::text AS source, i.silent, i.bystander_mode, i.lat, i.lng,
                   LEFT(i.description, 180) AS description_preview, i.created_at, i.resolved_at,
                   EXTRACT(EPOCH FROM (NOW() - i.created_at))::int AS age_seconds,
                   COALESCE(n.notification_count, 0)::int AS notifications_sent,
                   f.feedback_rating
            FROM incidents i
            LEFT JOIN (
                SELECT incident_id, COUNT(*) AS notification_count
                FROM notification_logs
                GROUP BY incident_id
            ) n ON n.incident_id = i.id
            LEFT JOIN (
                SELECT incident_id, AVG(rating)::float AS feedback_rating
                FROM feedback
                GROUP BY incident_id
            ) f ON f.incident_id = i.id
            WHERE i.status IN ('active', 'acknowledged', 'escalated')
            ORDER BY i.created_at DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    return [DashboardIncident(**dict(row)) for row in result.mappings().all()]


@router.get("/metrics", response_model=DashboardMetrics)
async def metrics(
    window_hours: int = Query(24, ge=1, le=24 * 30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_dispatcher),
):
    params = {"window_hours": window_hours}
    status_result = await db.execute(
        text(
            """
            SELECT status::text AS status, COUNT(*)::int AS count
            FROM incidents
            WHERE created_at >= NOW() - (:window_hours || ' hours')::interval
            GROUP BY status
            """
        ),
        params,
    )
    status_counts = {row.status: row.count for row in status_result.mappings().all()}

    priority_result = await db.execute(
        text(
            """
            SELECT priority::text AS priority, COUNT(*)::int AS count
            FROM incidents
            WHERE created_at >= NOW() - (:window_hours || ' hours')::interval
            GROUP BY priority
            """
        ),
        params,
    )
    priority_counts = {row.priority: row.count for row in priority_result.mappings().all()}

    resolution_result = await db.execute(
        text(
            """
            SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)))::float AS avg_resolution_seconds
            FROM incidents
            WHERE resolved_at IS NOT NULL
              AND created_at >= NOW() - (:window_hours || ' hours')::interval
            """
        ),
        params,
    )
    avg_resolution_seconds = resolution_result.scalar_one_or_none()

    rating_result = await db.execute(
        text(
            """
            SELECT AVG(f.rating)::float AS avg_feedback_rating
            FROM feedback f
            JOIN incidents i ON i.id = f.incident_id
            WHERE i.created_at >= NOW() - (:window_hours || ' hours')::interval
            """
        ),
        params,
    )
    avg_feedback_rating = rating_result.scalar_one_or_none()

    channel_result = await db.execute(
        text(
            """
            SELECT channel, COUNT(*)::int AS count
            FROM notification_logs
            WHERE created_at >= NOW() - (:window_hours || ' hours')::interval
            GROUP BY channel
            """
        ),
        params,
    )
    notifications_by_channel = {row.channel: row.count for row in channel_result.mappings().all()}

    notif_status_result = await db.execute(
        text(
            """
            SELECT status, COUNT(*)::int AS count
            FROM notification_logs
            WHERE created_at >= NOW() - (:window_hours || ' hours')::interval
            GROUP BY status
            """
        ),
        params,
    )
    notifications_by_status = {row.status: row.count for row in notif_status_result.mappings().all()}

    return DashboardMetrics(
        window_hours=window_hours,
        active_incidents=status_counts.get("active", 0),
        escalated_incidents=status_counts.get("escalated", 0),
        resolved_incidents=status_counts.get("resolved", 0),
        cancelled_incidents=status_counts.get("cancelled", 0),
        avg_resolution_seconds=avg_resolution_seconds,
        avg_feedback_rating=avg_feedback_rating,
        incidents_by_priority=priority_counts,
        notifications_by_channel=notifications_by_channel,
        notifications_by_status=notifications_by_status,
    )


@router.get("/incidents/{incident_id}/timeline", response_model=list[IncidentTimelineEvent])
async def incident_timeline(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_dispatcher),
):
    exists = await db.execute(text("SELECT 1 FROM incidents WHERE id = :incident_id"), {"incident_id": incident_id})
    if exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    result = await db.execute(
        text(
            """
            SELECT 'notification' AS event_type, created_at, channel, recipient_type, recipient, status, payload
            FROM notification_logs
            WHERE incident_id = :incident_id
<<<<<<< HEAD
            UNION ALL
            SELECT 'responder_attempt' AS event_type, created_at, channel, responder_type AS recipient_type,
                   responder_id::text AS recipient, status, payload
            FROM incident_responder_attempts
            WHERE incident_id = :incident_id
=======
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
            ORDER BY created_at ASC
            """
        ),
        {"incident_id": incident_id},
    )
    return [IncidentTimelineEvent(**dict(row)) for row in result.mappings().all()]


@router.websocket("/ws")
async def dashboard_websocket(websocket: WebSocket):
    try:
        async with AsyncSessionLocal() as db:
            user = await authenticate_websocket_user(websocket, db)
            if user.role not in {"dispatcher", "judge", "admin"}:
                await websocket.close(code=1008, reason="Insufficient role")
                return
        await websocket_manager.stream_dashboard(websocket)
    except WebSocketDisconnect:
        return
    except RuntimeError:
        return
