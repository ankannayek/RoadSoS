from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.cache import cache
from app.services.geohash import encode_geohash


def _clamp_radius(radius_km: int) -> int:
    return max(1, min(radius_km, settings.MAX_RADIUS_KM))


async def find_nearby_volunteers(
    lat: float,
    lng: float,
    db: AsyncSession,
    radius_km: int | None = None,
    limit: int | None = None,
    required_skills: Optional[List[str]] = None,
) -> List[Dict]:
    """PostGIS KNN search ranked by distance, rating, recency, and skill match."""
    radius_km = _clamp_radius(radius_km or settings.DEFAULT_RADIUS_KM)
    limit = min(limit or settings.MAX_VOLUNTEERS_RETURN, settings.MAX_VOLUNTEERS_RETURN)
    radius_meters = radius_km * 1000
    required_skills = required_skills or []

    query = text(
        """
        WITH origin AS (
          SELECT ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography AS point
        )
        SELECT
          v.id,
          v.user_id,
          v.name,
          v.phone,
          v.rating,
          COALESCE(v.skills, ARRAY[]::text[]) AS skills,
          v.lat,
          v.lng,
          ROUND((ST_Distance(v.location, origin.point) / 1000)::numeric, 3) AS distance_km,
          ROUND((
            LEAST(GREATEST(v.rating / 5.0, 0), 1) * 0.45 +
            GREATEST(0, 1 - (ST_Distance(v.location, origin.point) / :radius)) * 0.35 +
            CASE WHEN v.last_active > NOW() - INTERVAL '15 minutes' THEN 0.15 ELSE 0.05 END +
            CASE WHEN CAST(:required_skills AS text[]) && COALESCE(v.skills, ARRAY[]::text[]) THEN 0.05 ELSE 0 END
          )::numeric, 3) AS confidence_score
        FROM volunteers v, origin
        WHERE v.available = true
          AND v.location IS NOT NULL
          AND ST_DWithin(v.location, origin.point, :radius)
          AND NOT EXISTS (
            SELECT 1 FROM incidents i
            WHERE i.accepted_responder_id = v.id
              AND i.status IN ('active', 'acknowledged', 'escalated')
          )
        ORDER BY confidence_score DESC, distance_km ASC
        LIMIT :limit
        """
    )
    result = await db.execute(
        query,
        {
            "lat": lat,
            "lng": lng,
            "radius": radius_meters,
            "limit": limit,
            "required_skills": required_skills,
        },
    )
    rows = result.mappings().all()
    return [dict(row) for row in rows]

async def find_nearby_services(
    lat: float,
    lng: float,
    db: AsyncSession,
    service_type: Optional[str] = None,
    types: Optional[List[str]] = None,
    radius_km: int | None = None,
    limit: int | None = None,
) -> List[Dict]:
    """Find nearby official emergency services."""
    radius_km = _clamp_radius(radius_km or settings.SERVICE_RADIUS_KM)
    limit = min(limit or settings.MAX_VOLUNTEERS_RETURN, 20)
    radius_meters = radius_km * 1000

    type_values = [service_type] if service_type else list(types or [])
    type_values = [
        value.strip().upper()
        for value in type_values
        if isinstance(value, str) and value.strip() and value.strip().replace("_", "").isalnum()
    ]
    params: dict[str, Any] = {"lat": lat, "lng": lng, "radius": radius_meters, "limit": limit}
    params["filter_types"] = bool(type_values)
    params["types"] = type_values[:10] or ["__NO_SERVICE_TYPE__"]

    query = text(
        """
        WITH origin AS (
          SELECT ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography AS point
        )
        SELECT
          s.id,
          s.name,
          s.type,
          s.phone,
          s.lat,
          s.lng,
          s.capacity,
          s.source,
          ROUND((ST_Distance(s.location, origin.point) / 1000)::numeric, 2) AS distance_km,
          -- Verification Score (0 to 1)
          CASE
            WHEN s.source = 'gov_api' THEN 1.0
            WHEN s.source = 'osm_verified' THEN 0.8
            WHEN s.source = 'user_report' THEN 0.5
            WHEN s.source = 'seed' THEN 0.6
            ELSE 0.4
          END AS score_verification,
          -- Freshness Score (0 to 1)
          GREATEST(0, 1.0 - (EXTRACT(EPOCH FROM (NOW() - COALESCE(s.updated_at, s.created_at))) / 86400 / 30.0)) AS score_freshness,
          -- Distance Penalty (0 to 1, inverse of distance normalized by radius)
          GREATEST(0, 1.0 - (ST_Distance(s.location, origin.point) / :radius)) AS score_distance,
          -- History/Capacity Base (0 to 1)
          LEAST(GREATEST((COALESCE(s.capacity, 10)::float / 100.0), 0.1), 1.0) AS score_history
        FROM emergency_services s, origin
        WHERE s.is_active = true
          AND s.location IS NOT NULL
          AND ST_DWithin(s.location, origin.point, :radius)
          AND (:filter_types = false OR s.type IN :types)
        """
    ).bindparams(bindparam("types", expanding=True))
    result = await db.execute(query, params)
    rows = result.mappings().all()

    ranked_services = []
    for row in rows:
        d = dict(row)
        # Trust Score Formula implementation
        trust_score = (
            (0.40 * d["score_verification"])
            + (0.25 * d["score_freshness"])
            + (0.20 * d["score_distance"])
            + (0.15 * float(d["score_history"]))
        )
        d["trust_score"] = round(trust_score, 3)

        # Build explainable trust string
        reasons = []
        if d["source"] == "gov_api":
            reasons.append("Gov Verified")
        elif d["source"] == "osm_verified":
            reasons.append("OSM Verified")
        else:
            reasons.append("Community Sourced")

        if d["distance_km"] < 5.0:
            reasons.append(f"Nearby ({d['distance_km']}km)")

        if d["score_freshness"] > 0.8:
            reasons.append("Recently Updated")

        d["explainable_trust"] = f"{int(trust_score * 100)}% Trust — " + " + ".join(reasons)

        # Clean up internal score fields
        del d["score_verification"]
        del d["score_freshness"]
        del d["score_distance"]
        del d["score_history"]

        ranked_services.append(d)

    # Sort primarily by trust score, secondarily by distance
    ranked_services.sort(key=lambda x: (-x["trust_score"], x["distance_km"]))
    return ranked_services[:limit]


async def get_offline_services_prefetch(lat: float, lng: float, db: AsyncSession, precision: int = 6) -> Dict:
    """Cache nearby official services by geohash for offline Flutter fallback."""
    geohash = encode_geohash(lat, lng, precision=precision)
    cache_key = f"offline_services:{geohash}"
    cached = await cache.get(cache_key)
    if cached:
        return cached
    services = await find_nearby_services(lat, lng, db=db, radius_km=30, limit=20)
    payload = {"geohash": geohash, "services": services, "ttl_seconds": 86400}
    await cache.set(cache_key, payload, ttl_seconds=86400)
    return payload
