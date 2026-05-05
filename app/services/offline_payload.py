import json
from typing import Any, Dict

from app.models.incident import Incident
from app.models.user import User


def generate_offline_payload(incident: Incident, services: list[Dict[str, Any]], contacts: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Generates a highly compact payload for caching or SMS/satellite transmission."""
    
    # Extract only the most critical information to keep payload tiny
    nearest_hospital = None
    for s in services:
        if s.get("type") in ("HOSPITAL", "TRAUMA"):
            nearest_hospital = s
            break
            
    priority = incident.priority.value if hasattr(incident.priority, "value") else str(incident.priority)
    short_id = incident.id.hex[:6]
    
    sms_text = f"RoadSoS {priority} {incident.lat},{incident.lng}. "
    
    if nearest_hospital:
        sms_text += f"Nearest: {nearest_hospital['name']} ({nearest_hospital['distance_km']}km). "
        
    sms_text += f"Link: roadsos.app/i/{short_id}"

    # Generate a compact JSON bundle for local caching
    cache_bundle = {
        "incident_id": str(incident.id),
        "priority": priority,
        "lat": incident.lat,
        "lng": incident.lng,
        "services": [
            {
                "id": str(s["id"]),
                "name": s["name"],
                "type": s["type"],
                "phone": s.get("phone"),
                "distance_km": s["distance_km"],
                "trust_score": s["trust_score"],
            }
            for s in services[:3] # Only cache top 3 for extreme compactness
        ],
        "emergency_contacts": [
            {"name": c.get("name"), "phone": c.get("phone")} for c in contacts[:2]
        ]
    }

    return {
        "sms_text": sms_text[:160], # Ensure it fits in a single standard SMS if possible
        "cache_bundle": cache_bundle,
        "qr_data": json.dumps({"i": str(incident.id), "p": priority, "l": [incident.lat, incident.lng]}, separators=(',', ':')),
        "cache_ttl_hours": 72
    }
