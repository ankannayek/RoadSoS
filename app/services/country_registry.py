from typing import Dict, List, Optional, Tuple

# Rough bounding boxes for major regions to provide offline fallback emergency numbers.
# Format: [min_lat, min_lng, max_lat, max_lng]
REGIONS = {
    "india": {
        "bbox": [8.0, 68.0, 37.0, 97.0],
        "numbers": {"ambulance": "108", "police": "100", "fire": "101", "general": "112"},
    },
    "usa": {
        "bbox": [24.0, -125.0, 49.0, -66.0],
        "numbers": {"general": "911", "ambulance": "911", "police": "911", "fire": "911"},
    },
    "europe_eu": {
        # Rough EU box (includes UK)
        "bbox": [35.0, -10.0, 71.0, 40.0],
        "numbers": {"general": "112", "ambulance": "112", "police": "112", "fire": "112"},
    },
    "uk": {
        "bbox": [49.0, -8.0, 61.0, 2.0],
        "numbers": {"general": "999", "ambulance": "999", "police": "999", "fire": "999", "alt": "112"},
    },
    "australia": {
        "bbox": [-44.0, 112.0, -10.0, 154.0],
        "numbers": {"general": "000", "ambulance": "000", "police": "000", "fire": "000", "alt": "112"},
    },
    "kenya": {
        "bbox": [-4.7, 33.9, 5.0, 41.9],
        "numbers": {"general": "999", "ambulance": "112", "police": "999", "fire": "999"},
    },
    "brazil": {
        "bbox": [-33.7, -73.9, 5.2, -34.7],
        "numbers": {"general": "190", "ambulance": "192", "police": "190", "fire": "193"},
    },
}

DEFAULT_NUMBERS = {
    "general": "112",
    "ambulance": "112",
    "police": "112",
    "fire": "112",
}


def get_country_fallback_numbers(lat: float, lng: float) -> Dict[str, str]:
    """Returns official emergency numbers based on rough geolocation.

    This ensures that even if local cached services are empty, the user
    ALWAYS receives a valid national fallback number to call.
    """
    for region, data in REGIONS.items():
        bbox: List[float] = data["bbox"]
        if bbox[0] <= lat <= bbox[2] and bbox[1] <= lng <= bbox[3]:
            return data["numbers"]

    return DEFAULT_NUMBERS
