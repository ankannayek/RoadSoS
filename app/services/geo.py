from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import text
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
        ORDER BY v.location <-> origin.point, confidence_score DESC
        LIMIT :limit
        """
    )
    result = await db.execute(
        query,
        {"lat": lat, "lng": lng, "radius": radius_meters, "limit": limit, "required_skills": required_skills},
    )
    return [dict(row) for row in result.mappings().all()]


async def find_nearby_services(
    lat: float,
    lng: float,
    db: AsyncSession,
    types: Optional[List[str]] = None,
    radius_km: int | None = None,
    limit: int = 8,
) -> List[Dict]:
    if types is None:
        types = ["AMBULANCE", "TRAUMA", "HOSPITAL", "POLICE", "FIRE", "TOWING"]
    radius_meters = _clamp_radius(radius_km or settings.SERVICE_RADIUS_KM) * 1000

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
          s.confidence_score,
          s.source,
          ROUND((ST_Distance(s.location, origin.point) / 1000)::numeric, 3) AS distance_km
        FROM emergency_services s, origin
        WHERE s.is_active = true
          AND s.type = ANY(CAST(:types AS text[]))
          AND ST_DWithin(s.location, origin.point, :radius)
        ORDER BY s.location <-> origin.point, s.confidence_score DESC
        LIMIT :limit
        """
    )
    result = await db.execute(query, {"lat": lat, "lng": lng, "types": types, "radius": radius_meters, "limit": limit})
    return [dict(row) for row in result.mappings().all()]


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
