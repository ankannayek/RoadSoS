import logging
import math
import time
import asyncio

from app.services.geohash import encode_geohash
from app.services.cache import cache

logger = logging.getLogger(__name__)

MCI_GEOHASH_PRECISION = 6
MCI_WINDOW_SECONDS = 300
DEFAULT_MCI_THRESHOLD = 3

_LOCAL_CELLS: dict[str, tuple[float, set[str]]] = {}
_LOCAL_LOCK = asyncio.Lock()


def mci_geohash_cell(lat: float, lng: float, precision: int = MCI_GEOHASH_PRECISION) -> str:
    return encode_geohash(lat, lng, precision=precision)


def mci_cell_key(cell: str) -> str:
    return f"mci:cluster:{cell}"


def is_mci_candidate_priority(priority: str) -> bool:
    return priority in {"P1_CRITICAL", "P2_HIGH", "P3_MEDIUM"}


async def get_mci_threshold() -> int:
    """Get the runtime-tunable MCI threshold, defaulting to 3."""
    try:
        threshold = await cache.get("mci:threshold")
    except Exception as exc:
        logger.warning("MCI threshold lookup failed; using default: %s", exc)
        return DEFAULT_MCI_THRESHOLD
    if threshold is None:
        return DEFAULT_MCI_THRESHOLD
    try:
        return max(2, int(threshold))
    except (TypeError, ValueError):
        logger.warning("Invalid mci:threshold value %r; using default", threshold)
        return DEFAULT_MCI_THRESHOLD


async def _register_local(key: str, incident_id: str) -> int:
    now = time.time()
    async with _LOCAL_LOCK:
        expires_at, members = _LOCAL_CELLS.get(key, (now + MCI_WINDOW_SECONDS, set()))
        if expires_at < now:
            members = set()
        members.add(incident_id)
        _LOCAL_CELLS[key] = (now + MCI_WINDOW_SECONDS, members)
        return len(members)


async def _local_members(key: str) -> list[str]:
    now = time.time()
    async with _LOCAL_LOCK:
        item = _LOCAL_CELLS.get(key)
        if not item:
            return []
        expires_at, members = item
        if expires_at < now:
            _LOCAL_CELLS.pop(key, None)
            return []
        return sorted(members)



async def register_sos_in_geohash(lat: float, lng: float, incident_id: str, *, cell: str | None = None) -> int:
    """
    Registers an SOS in a precise geohash cell.
    Returns the number of concurrent SOS requests in the cell (the cluster size).
    """
    cell = cell or mci_geohash_cell(lat, lng)
    key = mci_cell_key(cell)

    redis_client = getattr(cache, "client", None)
    if redis_client is not None:
        try:
            script = """
            redis.call('SADD', KEYS[1], ARGV[1])
            redis.call('EXPIRE', KEYS[1], ARGV[2])
            return redis.call('SCARD', KEYS[1])
            """
            return int(await redis_client.eval(script, 1, key, incident_id, MCI_WINDOW_SECONDS))
        except Exception as exc:
            logger.warning("Redis MCI registration failed; using process-local fallback: %s", exc)

    return await _register_local(key, incident_id)


async def get_sos_ids_in_geohash(cell: str) -> list[str]:
    key = mci_cell_key(cell)
    redis_client = getattr(cache, "client", None)
    if redis_client is not None:
        try:
            return sorted(str(member) for member in await redis_client.smembers(key))
        except Exception as exc:
            logger.warning("Redis MCI member lookup failed; using process-local fallback: %s", exc)
    return await _local_members(key)


def mci_resource_estimate(cluster_size: int, avg_priority: float = 0.0) -> dict:
    """Estimates the resources required for an MCI based on cluster size."""
    cluster_size = max(0, int(cluster_size))
    severity = avg_priority or 2.0
    if severity <= 1.5:
        p1_ratio, p2_ratio = 0.50, 0.35
    elif severity <= 2.5:
        p1_ratio, p2_ratio = 0.40, 0.35
    else:
        p1_ratio, p2_ratio = 0.25, 0.40

    p1_estimate = min(cluster_size, math.ceil(cluster_size * p1_ratio))
    p2_estimate = min(max(0, cluster_size - p1_estimate), math.ceil(cluster_size * p2_ratio))
    ambulances = max(2, math.ceil((p1_estimate + p2_estimate) / 2)) if cluster_size else 0
    return {
        "estimated_victims": cluster_size,
        "estimated_p1": p1_estimate,
        "estimated_p2": p2_estimate,
        "ambulances_recommended": ambulances,
        "triage_protocol": "START",  # Simple Triage and Rapid Treatment
        "command_post_radius_m": 150
    }
