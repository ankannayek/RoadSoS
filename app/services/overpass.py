from __future__ import annotations

import logging
from typing import Any, Dict

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import EmergencyService
from app.services.task_queue import task_queue

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def _build_query(lat: float, lng: float, radius_km: float = 15.0) -> str:
    """Builds an Overpass QL query to find emergency services in a bounding box."""
    # Rough bounding box calculation (1 degree lat ~= 111km)
    delta = radius_km / 111.0
    min_lat, min_lng = lat - delta, lng - delta
    max_lat, max_lng = lat + delta, lng + delta
    
    bbox = f"{min_lat},{min_lng},{max_lat},{max_lng}"
    
    return f"""
    [out:json][timeout:25];
    (
      nwr["amenity"="hospital"]["emergency"="yes"]({bbox});
      nwr["amenity"="police"]({bbox});
      nwr["amenity"="fire_station"]({bbox});
      nwr["shop"="car_repair"]["service"="tyres"]({bbox});
    );
    out center;
    """

async def fetch_and_seed_services(lat: float, lng: float, db: AsyncSession, radius_km: float = 15.0) -> int:
    """Fetches real emergency services from OpenStreetMap and saves them to the DB.
    
    This runs in the background. It provides massive credibility by pulling verified
    free data globally.
    """
    query = _build_query(lat, lng, radius_km)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(OVERPASS_URL, data={"data": query})
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.warning(f"Overpass API fetch failed: {e}")
        return 0

    elements = data.get("elements", [])
    if not elements:
        return 0

    added_count = 0
    for el in elements:
        tags = el.get("tags", {})
        
        # Determine service type
        service_type = None
        if tags.get("amenity") == "hospital":
            if tags.get("emergency") == "yes":
                service_type = "TRAUMA" if "trauma" in tags.get("healthcare:speciality", "").lower() else "HOSPITAL"
        elif tags.get("amenity") == "police":
            service_type = "POLICE"
        elif tags.get("amenity") == "fire_station":
            service_type = "FIRE"
        elif tags.get("shop") == "car_repair" and tags.get("service") == "tyres":
            service_type = "TOWING" # Re-using towing for vehicle repair in our schema
            
        if not service_type:
            continue
            
        name = tags.get("name") or tags.get("name:en") or f"Unknown {service_type}"
        phone = tags.get("phone") or tags.get("contact:phone")
        
        el_lat = el.get("lat") or el.get("center", {}).get("lat")
        el_lng = el.get("lon") or el.get("center", {}).get("lon")
        
        if not el_lat or not el_lng:
            continue

        # Check if already exists nearby (simple deduplication)
        # Using a simplistic distance check or just name+type. 
        # In a real heavy production app we'd use PostGIS ST_DWithin here.
        # For efficiency in this background worker, we just check name.
        existing = await db.execute(
            select(EmergencyService.id).where(
                EmergencyService.name == name,
                EmergencyService.type == service_type
            )
        )
        if existing.scalar_one_or_none():
            continue

        service = EmergencyService(
            name=name[:150],
            type=service_type,
            phone=phone[:20] if phone else None,
            lat=el_lat,
            lng=el_lng,
            source="osm_verified",
            confidence_score=0.80, # High trust for OSM
            metadata_json={"osm_id": el.get("id"), "tags": tags}
        )
        db.add(service)
        added_count += 1

    if added_count > 0:
        await db.commit()
        logger.info(f"Overpass seeder added {added_count} verified services around {lat}, {lng}.")
        
    return added_count


async def handle_seed_overpass_bbox(payload: dict) -> None:
    """Task queue handler to run the seeder in the background without blocking SOS."""
    lat = payload.get("lat")
    lng = payload.get("lng")
    if lat is None or lng is None:
        return
        
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await fetch_and_seed_services(lat, lng, db)

task_queue.register("seed_overpass_bbox", handle_seed_overpass_bbox)
