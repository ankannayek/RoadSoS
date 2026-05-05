import pytest

from app.services.classifier import classify_emergency


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("person unconscious not breathing after crash", "P1_CRITICAL"),
        ("heavy bleeding from leg, blood everywhere", "P1_CRITICAL"),
        ("driver trapped inside vehicle, cannot open door", "P1_CRITICAL"),
        ("car fire on highway, smoke everywhere", "P1_CRITICAL"),
        ("car in water, person drowning", "P1_CRITICAL"),
        ("multi vehicle pileup on highway", "P1_CRITICAL"),
        ("passenger choking, cannot breathe", "P1_CRITICAL"),
        ("person stabbed, knife wound visible", "P1_CRITICAL"),
        ("driver having chest pain while driving", "P2_HIGH"),
        ("motorcycle rider down on road", "P2_HIGH"),
        ("pedestrian hit by car at crossing", "P2_HIGH"),
        ("aggressive driver threatening us, road rage", "P2_HIGH"),
        ("fuel leak from tanker, gas smell everywhere", "P2_HIGH"),
        ("electric vehicle crash, battery fire visible", "P2_HIGH"),
        ("child injured in back seat", "P2_HIGH"),
        ("minor fender bender, vehicle damage", "P3_MEDIUM"),
        ("feeling dizzy and dehydration", "P3_MEDIUM"),
        ("got a flat tire on side road", "P4_LOW"),
        ("out of fuel, need help", "P4_LOW"),
        ("locked out of car, key stuck", "P4_LOW"),
    ],
)
def test_classifier_simulation_matrix(description, expected):
    priority, _ = classify_emergency(description)
    assert priority == expected


def test_classifier_defaults_ambiguous_road_emergency_to_medium():
    priority, confidence = classify_emergency("something happened near the road")
    assert priority == "P3_MEDIUM"
    assert confidence == 0.50


def test_classifier_uses_sensor_override_for_critical_crash():
    priority, confidence = classify_emergency("impact detected", impact_force=9.0, sensor_payload={"airbag_deployed": True})
    assert priority == "P1_CRITICAL"
    assert confidence == 1.0


def test_sensor_plus_p1_text_gives_max_confidence():
    priority, confidence = classify_emergency("person unconscious, major bleeding", impact_force=6.0)
    assert priority == "P1_CRITICAL"
    assert confidence == 1.0


def test_compound_medical_p2_escalates_to_p1():
    priority, _ = classify_emergency("chest pain and seizure while driving, child in car")
    assert priority == "P1_CRITICAL"


def test_noncritical_multi_p2_stays_p2():
    priority, _ = classify_emergency("motorcycle rider down on road")
    assert priority == "P2_HIGH"


def test_silent_sos_upgrades_to_p2():
    priority, _ = classify_emergency("need help", source="silent")
    assert priority == "P2_HIGH"


def test_bystander_upgrades_p4_to_p3():
    priority, _ = classify_emergency("flat tire on highway", source="bystander")
    assert priority == "P3_MEDIUM"
