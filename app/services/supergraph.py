from __future__ import annotations

import logging
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select, text

from app.db.session import AsyncSessionLocal
from app.models.incident import Incident
from app.services.event_bus import event_bus
from app.services.mci import get_mci_threshold, get_sos_ids_in_geohash, mci_resource_estimate
from app.services.task_queue import task_queue
from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)

DBSCAN_EPS_METERS = 300
DBSCAN_WINDOW_MINUTES = 10
DBSCAN_PREFILTER_METERS = 2000

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PRIORITY_SCORE = {"P1_CRITICAL": 1.0, "P2_HIGH": 2.0, "P3_MEDIUM": 3.0, "P4_LOW": 4.0}
_FAMILY_TERMS = {
    "traffic": (
        "accident",
        "bike",
        "bus",
        "car",
        "collision",
        "crash",
        "highway",
        "pileup",
        "rollover",
        "scooter",
        "truck",
        "vehicle",
    ),
    "fire": ("burn", "explosion", "fire", "flame", "smoke"),
    "hazmat": ("chemical", "diesel", "fuel", "gas", "hazmat", "leak", "petrol", "tanker"),
    "medical": (
        "allergic",
        "asthma",
        "breathing",
        "cardiac",
        "chest",
        "fainting",
        "heart",
        "seizure",
        "stroke",
        "unconscious",
    ),
    "violence": ("assault", "attacked", "gun", "knife", "robbery", "stabbed", "weapon"),
    "weather": ("flood", "landslide", "rain", "storm", "tree", "water"),
}


def _priority_value(priority: str) -> float:
    return _PRIORITY_SCORE.get(str(priority), 4.0)


def _cluster_priority_is_consistent(rows: Iterable) -> bool:
    values = [_priority_value(row.priority) for row in rows]
    if not values or any(value >= 4.0 for value in values):
        return False
    return max(values) - min(values) <= 2.0


def _incident_family(description: str | None) -> str:
    lowered = (description or "").lower()
    tokens = set(_TOKEN_RE.findall(lowered))
    for family, terms in _FAMILY_TERMS.items():
        if any(term in lowered or term in tokens for term in terms):
            return family
    return "unknown"


def _cluster_semantics_are_consistent(rows: Iterable) -> bool:
    families = [_incident_family(row.description) for row in rows]
    known = [family for family in families if family != "unknown"]
    if len(known) <= 1:
        return True
    dominant = Counter(known).most_common(1)[0][1]
    return dominant / len(known) >= 0.67


async def _publish_downgrade(cell: str | None, trigger_incident_id: str | None, reason: str) -> None:
    incident_ids = await get_sos_ids_in_geohash(cell) if cell else []
    if trigger_incident_id:
        incident_ids.append(str(trigger_incident_id))
    unique_incident_ids = sorted(set(incident_ids))
    payload = {
        "reason": reason,
        "message": "MCI suspected flag cleared. Treat this as an individual SOS.",
    }

    async with AsyncSessionLocal() as db:
        valid_uuids: list[uuid.UUID] = []
        for item in unique_incident_ids:
            try:
                valid_uuids.append(uuid.UUID(str(item)))
            except ValueError:
                logger.warning("Skipping invalid incident id in MCI downgrade: %s", item)
        if valid_uuids:
            result = await db.execute(select(Incident).where(Incident.id.in_(valid_uuids)))
            for incident in result.scalars().all():
                metadata = dict(incident.metadata_json or {})
                metadata.update(
                    {
                        "mci_pending": False,
                        "mci_downgrade_reason": reason,
                        "mci_downgraded_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                incident.metadata_json = metadata
            await db.commit()

    for incident_id in unique_incident_ids:
        await websocket_manager.publish_incident_event(incident_id, "mci_downgrade", payload)
    await websocket_manager.publish_dashboard_event("mci_downgrade", {"incident_ids": unique_incident_ids, **payload})


async def _confirm_cluster(cluster_rows: list) -> None:
    cluster_rows.sort(key=lambda row: row.created_at)
    coordinator_id = cluster_rows[0].id
    mci_cluster_id = uuid.uuid4()
    cluster_incident_ids = [row.id for row in cluster_rows]
    victim_ids = [str(incident_id) for incident_id in cluster_incident_ids]
    avg_priority = sum(_priority_value(row.priority) for row in cluster_rows) / len(cluster_rows)
    resources = mci_resource_estimate(len(cluster_rows), avg_priority)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Incident).where(Incident.id.in_(cluster_incident_ids)))
        incidents = result.scalars().all()
        for incident in incidents:
            metadata = dict(incident.metadata_json or {})
            metadata.update(
                {
                    "mci_pending": False,
                    "mci_confirmed_at": datetime.now(timezone.utc).isoformat(),
                    "mci_resources": resources,
                }
            )
            incident.cluster_id = mci_cluster_id
            incident.is_mci = True
            incident.is_mci_coordinator = incident.id == coordinator_id
            incident.metadata_json = metadata
        await db.commit()

    payload = {
        "cluster_id": str(mci_cluster_id),
        "coordinator_id": str(coordinator_id),
        "victims": victim_ids,
        "resources": resources,
        "message": "MCI confirmed. Unified command brief follows.",
    }
    await event_bus.publish(f"mci:cluster:{mci_cluster_id}", {"type": "mci_confirmed", **payload})
    for incident_id in victim_ids:
        await websocket_manager.publish_incident_event(incident_id, "mci_confirmed", payload)
    await websocket_manager.publish_dashboard_event("mci_confirmed", payload)
    logger.info("MCI confirmed: cluster_id=%s size=%s coordinator=%s", mci_cluster_id, len(cluster_rows), coordinator_id)


async def mci_dbscan_handler(payload: dict) -> None:
    lat = payload.get("lat")
    lng = payload.get("lng")
    cell = payload.get("cell")
    trigger_incident_id = payload.get("trigger_incident_id")
    if lat is None or lng is None:
        logger.error("mci_dbscan payload missing lat/lng")
        return

    threshold = await get_mci_threshold()
    query = text(
        """
        WITH recent_incidents AS (
            SELECT id, created_at, priority::text AS priority, description, location
            FROM incidents
            WHERE created_at >= NOW() - (:window_minutes * INTERVAL '1 minute')
              AND status::text NOT IN ('resolved', 'cancelled')
              AND priority::text <> 'P4_LOW'
              AND location IS NOT NULL
              AND ST_DWithin(location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :prefilter_meters)
        ),
        clusters AS (
            SELECT id, created_at, priority, description,
                   ST_ClusterDBSCAN(
                       ST_Transform(location::geometry, 3857),
                       eps := :eps_meters,
                       minpoints := :threshold
                   ) OVER () AS dbscan_cluster_id
            FROM recent_incidents
        )
        SELECT id, created_at, priority, description, dbscan_cluster_id
        FROM clusters
        WHERE dbscan_cluster_id IS NOT NULL
        """
    )

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            query,
            {
                "lng": lng,
                "lat": lat,
                "threshold": threshold,
                "window_minutes": DBSCAN_WINDOW_MINUTES,
                "prefilter_meters": DBSCAN_PREFILTER_METERS,
                "eps_meters": DBSCAN_EPS_METERS,
            },
        )
        rows = result.fetchall()

    clusters: dict[int, list] = {}
    for row in rows:
        clusters.setdefault(row.dbscan_cluster_id, []).append(row)

    if trigger_incident_id:
        clusters = {
            cluster_id: cluster_rows
            for cluster_id, cluster_rows in clusters.items()
            if any(str(row.id) == str(trigger_incident_id) for row in cluster_rows)
        }

    for cluster_rows in clusters.values():
        if len(cluster_rows) < threshold:
            continue
        if not _cluster_priority_is_consistent(cluster_rows):
            await _publish_downgrade(cell, trigger_incident_id, "priority_mismatch")
            return
        if not _cluster_semantics_are_consistent(cluster_rows):
            await _publish_downgrade(cell, trigger_incident_id, "semantic_mismatch")
            return
        await _confirm_cluster(cluster_rows)
        return

    await _publish_downgrade(cell, trigger_incident_id, "dbscan_not_confirmed")


task_queue.register("mci_dbscan", mci_dbscan_handler)
