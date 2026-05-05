from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


@dataclass(frozen=True)
class Rule:
    priority: str
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
    """
    text = (description or "").lower().strip()
    sensor_payload = sensor_payload or {}

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


def response_eta(priority: str) -> str:
    return {
        "P1_CRITICAL": "2-6 minutes if responders are nearby; official services escalated immediately.",
        "P2_HIGH": "3-8 minutes; nearby volunteers and services are being notified.",
        "P3_MEDIUM": "5-12 minutes; nearby helpers are being matched.",
        "P4_LOW": "10-20 minutes; non-critical assistance is being matched.",
    }.get(priority, "5-12 minutes")
