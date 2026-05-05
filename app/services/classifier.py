from __future__ import annotations

from dataclasses import dataclass
<<<<<<< HEAD
from typing import Dict, Tuple
=======
from typing import Dict, Iterable, Tuple
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0


@dataclass(frozen=True)
class Rule:
    priority: str
<<<<<<< HEAD
    base_score: float
    terms: tuple[str, ...]


# Deterministic triage term banks. Keep these conservative: SOS dispatch should
# avoid false negatives, but ordinary P2/P4 cases must not become P1 without a
# clear life-threat signal.
P1_TERMS: tuple[str, ...] = (
    "not breathing",
    "unconscious",
    "unresponsive",
    "not responding",
    "no pulse",
    "no heartbeat",
    "cardiac arrest",
    "heart stopped",
    "only gasping",
    "gasping",
    "stopped breathing",
    "cannot breathe",
    "major bleeding",
    "heavy bleeding",
    "bleeding out",
    "blood everywhere",
    "blood not stopping",
    "blood won't stop",
    "deep cut",
    "amputation",
    "limb severed",
    "arterial bleeding",
    "severe head injury",
    "skull fracture",
    "cannot move legs",
    "paralyzed",
    "spinal injury",
    "trapped",
    "pinned",
    "crushed",
    "stuck under vehicle",
    "cannot open door",
    "stuck inside",
    "vehicle fire",
    "car fire",
    "engine fire",
    "explosion",
    "person on fire",
    "smoke inhalation",
    "electrocuted",
    "electric shock",
    "high voltage",
    "exposed wire",
    "exposed cable",
    "drowning",
    "submerged",
    "sinking",
    "car in water",
    "vehicle in water",
    "swept away",
    "severe crash",
    "rollover",
    "hit and run injured",
    "pileup",
    "multi vehicle",
    "multiple vehicles",
    "head on collision",
    "wrong way driver",
    "gunshot",
    "stabbed",
    "knife wound",
    "shot",
    "machete",
    "gun visible",
    "knife visible",
    "weapon visible",
    "heart attack",
    "cardiac",
    "choking",
    "child not breathing",
    "baby not breathing",
    "infant choking",
)

P2_TERMS: tuple[str, ...] = (
    "head injury",
    "neck pain after crash",
    "back pain after crash",
    "helmet damage",
    "thrown from bike",
    "ev crash",
    "electric vehicle",
    "hybrid vehicle",
    "battery fire",
    "orange cable",
    "battery leak",
    "fuel leak",
    "petrol leak",
    "diesel leak",
    "gas smell",
    "chemical spill",
    "hazmat",
    "hazardous material",
    "fumes",
    "tanker",
    "chemical leak",
    "bike accident",
    "motorcycle",
    "scooter crash",
    "rider down",
    "pedestrian hit",
    "cyclist hit",
    "hit by car",
    "person on road",
    "run over",
    "highway crash",
    "highway accident",
    "breakdown in traffic",
    "stalled in traffic",
    "highway breakdown",
    "stranded on highway",
    "assault",
    "harassment",
    "followed",
    "robbery",
    "stalking",
    "road rage",
    "threat",
    "weapon",
    "aggressive driver",
    "chased",
    "attacked",
    "breathing problem",
    "chest pain",
    "stroke",
    "seizure",
    "fracture",
    "broken bone",
    "allergic reaction",
    "anaphylaxis",
    "diabetic emergency",
    "fainting",
    "asthma attack",
    "pregnant",
    "child injured",
    "elderly injured",
    "child in car",
    "baby in car",
    "pregnant woman",
    "elderly person",
    "disabled person",
    "wheelchair",
    "heatstroke",
    "hypothermia",
    "heat exhaustion",
    "animal collision",
    "cow on road",
    "deer on road",
    "livestock on highway",
    "landslide",
    "tree fallen",
    "road blocked",
    "debris on road",
    "stranded at night",
    "alone at night",
)

P3_TERMS: tuple[str, ...] = (
    "injury",
    "pain",
    "stuck",
    "minor bleeding",
    "lost",
    "panic",
    "sprain",
    "unable to move",
    "stranded",
    "accident",
    "collision",
    "fender bender",
    "car crash",
    "vehicle damage",
    "dent",
    "bumper",
    "cannot move",
    "dehydration",
    "exhaustion",
    "dizzy",
    "nauseous",
    "confusion",
    "disoriented",
    "vomiting",
    "stuck in rain",
    "cold",
    "faint",
    "animal on road",
    "dog on road",
)

P4_TERMS: tuple[str, ...] = (
    "flat tire",
    "puncture",
    "tyre burst",
    "breakdown",
    "battery dead",
    "out of fuel",
    "tow",
    "mechanic",
    "lost keys",
    "locked out",
    "key stuck",
    "overheating",
    "radiator",
    "engine light",
    "check engine",
    "coolant",
    "windshield cracked",
    "wiper broken",
    "headlight broken",
    "fog light",
)

RULES: tuple[Rule, ...] = (
    Rule("P1_CRITICAL", 0.97, P1_TERMS),
    Rule("P2_HIGH", 0.84, P2_TERMS),
    Rule("P4_LOW", 0.35, P4_TERMS),
    Rule("P3_MEDIUM", 0.62, P3_TERMS),
)

EMERGENCY_KEYWORDS: frozenset[str] = frozenset(
    P1_TERMS
    + tuple(
        term
        for term in P2_TERMS
        if term
        in {
            "chest pain",
            "stroke",
            "seizure",
            "anaphylaxis",
            "assault",
            "weapon",
            "attacked",
            "pedestrian hit",
            "cyclist hit",
            "fuel leak",
            "chemical spill",
            "battery fire",
            "ev crash",
            "heatstroke",
            "hypothermia",
            "breathing problem",
            "asthma attack",
        }
    )
)

P1_CONTEXT_TERMS = (
    "not breathing",
    "unconscious",
    "unresponsive",
    "no pulse",
    "heavy bleeding",
    "major bleeding",
    "blood everywhere",
    "vehicle fire",
    "car fire",
    "engine fire",
    "explosion",
    "trapped",
    "pinned",
    "drowning",
)

FUEL_OR_CHEMICAL_TERMS = ("fuel leak", "petrol leak", "diesel leak", "gas smell", "chemical spill", "chemical leak", "tanker")
FIRE_OR_EXPLOSION_TERMS = ("vehicle fire", "car fire", "engine fire", "explosion", "person on fire")
PEDESTRIAN_OR_RIDER_TERMS = ("pedestrian hit", "cyclist hit", "hit by car", "run over", "motorcycle", "rider down", "bike accident")
MEDICAL_COMPOUND_TERMS = ("chest pain", "stroke", "seizure", "breathing problem", "anaphylaxis")


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _count_hits(text: str, terms: tuple[str, ...]) -> int:
    return sum(1 for term in terms if term in text)


def _compound_critical(text: str) -> bool:
    if _contains_any(text, FUEL_OR_CHEMICAL_TERMS) and _contains_any(text, FIRE_OR_EXPLOSION_TERMS):
        return True
    if _contains_any(text, PEDESTRIAN_OR_RIDER_TERMS) and _contains_any(text, P1_CONTEXT_TERMS):
        return True
    if _count_hits(text, MEDICAL_COMPOUND_TERMS) >= 2:
        return True
    return False


def classify_emergency(
    description: str,
    impact_force: float = 0,
    sensor_payload: Dict | None = None,
    *,
    source: str = "manual",
) -> Tuple[str, float]:
    """Fast deterministic triage.

    The SOS path must stay auditable and low latency, so this function uses
    explicit rules only. P1 is reserved for clear life threat or critical
    sensors; diverse serious road events remain P2 unless they include P1
    context.
=======
    score: float
    terms: tuple[str, ...]


RULES: tuple[Rule, ...] = (
    Rule("P1_CRITICAL", 0.99, ("not breathing", "unconscious", "no pulse", "cardiac arrest", "major bleeding", "heavy bleeding", "head injury", "trapped", "rollover", "vehicle fire", "explosion", "drowning", "electric shock", "severe crash", "hit and run injured")),
    Rule("P2_HIGH", 0.84, ("breathing problem", "chest pain", "stroke", "seizure", "fracture", "broken bone", "pregnant", "child injured", "elderly injured", "bike accident", "motorcycle", "assault", "harassment", "followed", "robbery")),
    Rule("P3_MEDIUM", 0.62, ("injury", "pain", "stuck", "minor bleeding", "lost", "panic", "sprain", "unable to move", "stranded")),
    Rule("P4_LOW", 0.35, ("flat tire", "puncture", "breakdown", "battery dead", "out of fuel", "tow", "mechanic", "lost keys")),
)


def classify_emergency(description: str, impact_force: float = 0, sensor_payload: Dict | None = None) -> Tuple[str, float]:
    """Fast deterministic triage.

    This intentionally does not call AI. SOS routing must be deterministic,
    auditable, and fast enough for immediate emergency response.
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
    """
    text = (description or "").lower().strip()
    sensor_payload = sensor_payload or {}

<<<<<<< HEAD
    sensor_critical = (
        impact_force >= 8.0
        or sensor_payload.get("airbag_deployed") is True
        or sensor_payload.get("rollover") is True
    )
    sensor_high = impact_force >= 5.0

    if sensor_critical:
        return "P1_CRITICAL", 1.0
    if sensor_high:
        if _contains_any(text, P1_TERMS):
            return "P1_CRITICAL", 1.0
        return "P2_HIGH", 0.90

    if _compound_critical(text):
        return "P1_CRITICAL", 0.94

    for rule in RULES:
        hits = _count_hits(text, rule.terms)
        if not hits:
            continue
        score = rule.base_score
        if rule.priority != "P1_CRITICAL":
            score = min(score + (0.02 if hits >= 2 else 0), 0.90)
        elif hits >= 2:
            score = min(score + 0.02, 0.99)
        priority, score = _apply_source_uplift(rule.priority, score, source)
        return priority, round(score, 2)

    priority, score = _apply_source_uplift("P3_MEDIUM", 0.50, source)
    return priority, round(score, 2)


def _apply_source_uplift(priority: str, score: float, source: str) -> Tuple[str, float]:
    priority_order = {"P1_CRITICAL": 0, "P2_HIGH": 1, "P3_MEDIUM": 2, "P4_LOW": 3}

    if source == "silent" and priority_order.get(priority, 3) > 1:
        return "P2_HIGH", max(score, 0.80)
    if source == "bystander" and priority_order.get(priority, 3) > 2:
        return "P3_MEDIUM", max(score, 0.60)
    return priority, score
=======
    # Sensor overrides for severe auto-detect events.
    if impact_force >= 8.0 or sensor_payload.get("airbag_deployed") is True or sensor_payload.get("rollover") is True:
        return "P1_CRITICAL", 1.0
    if impact_force >= 5.0:
        return "P2_HIGH", 0.82

    for rule in RULES:
        if any(term in text for term in rule.terms):
            return rule.priority, rule.score

    # Default to medium instead of low because ambiguous road emergencies can deteriorate.
    return "P3_MEDIUM", 0.50
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0


def response_eta(priority: str) -> str:
    return {
        "P1_CRITICAL": "2-6 minutes if responders are nearby; official services escalated immediately.",
        "P2_HIGH": "3-8 minutes; nearby volunteers and services are being notified.",
        "P3_MEDIUM": "5-12 minutes; nearby helpers are being matched.",
        "P4_LOW": "10-20 minutes; non-critical assistance is being matched.",
    }.get(priority, "5-12 minutes")
