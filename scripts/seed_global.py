import asyncio
import logging
import sys

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_global")

from app.db.session import AsyncSessionLocal
from app.services.overpass import fetch_and_seed_services

# Demo locations showcasing global applicability
SCENARIOS = {
    "Delhi, India (Dense Urban)": {"lat": 28.6139, "lng": 77.2090},
    "San Francisco, USA (Highway/Urban)": {"lat": 37.7749, "lng": -122.4194},
    "Nairobi, Kenya (Developing/Rural-adjacent)": {"lat": -1.2921, "lng": 36.8219},
    "Berlin, Germany (European Network)": {"lat": 52.5200, "lng": 13.4050},
    "Rural Outback, Australia (Sparse)": {"lat": -23.6980, "lng": 133.8807},
}

async def run_seeder():
    logger.info("Starting Global Reproducibility Seeder...")
    logger.info("This will fetch live verified emergency services from OpenStreetMap.")
    
    async with AsyncSessionLocal() as db:
        for name, coords in SCENARIOS.items():
            logger.info(f"\nSeeding scenario: {name} (Lat: {coords['lat']}, Lng: {coords['lng']})")
            
            # Fetch and seed
            added = await fetch_and_seed_services(coords['lat'], coords['lng'], db, radius_km=15.0)
            
            if added > 0:
                logger.info(f"✅ Success: Seeded {added} real-world verified services.")
            else:
                logger.warning(f"⚠️ No new services found or fetch failed for {name}.")
                
            # Sleep briefly to respect Overpass rate limits
            await asyncio.sleep(2)
            
    logger.info("\nGlobal seeding complete! The Golden Hour Rescue Engine is ready for demo.")

if __name__ == "__main__":
    # Ensure this is run from the project root
    try:
        asyncio.run(run_seeder())
    except KeyboardInterrupt:
        logger.info("Seeding cancelled by user.")
        sys.exit(1)
