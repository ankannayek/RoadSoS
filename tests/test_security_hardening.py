from __future__ import annotations

import base64
import hmac
import json
from types import SimpleNamespace
from uuid import uuid4

from starlette.requests import Request

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.services.offline_payload import generate_offline_payload
from app.services.rate_limiter import client_identifier


def _request(client_host: str, forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))
    return Request(
        {
            "type": "http",
            "headers": headers,
            "client": (client_host, 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "method": "GET",
            "path": "/",
        }
    )


def test_password_hashing_does_not_truncate_after_72_bytes():
    password = "a" * 72 + "x"
    different_tail = "a" * 72 + "y"
    hashed = get_password_hash(password)

    assert verify_password(password, hashed)
    assert not verify_password(different_tail, hashed)


def test_rate_limiter_ignores_spoofed_forwarded_for_by_default(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)

    with_forwarded = client_identifier(_request("9.9.9.9", forwarded_for="1.2.3.4"))
    without_forwarded = client_identifier(_request("9.9.9.9"))

    assert with_forwarded == without_forwarded


def test_offline_payload_includes_valid_mesh_relay_signature():
    incident = SimpleNamespace(id=uuid4(), priority="P1_CRITICAL", lat=13.0067, lng=80.2206)
    payload = generate_offline_payload(incident, services=[], contacts=[])
    relay_packet = payload["relay_packet"]

    decoded = json.loads(base64.b64decode(relay_packet["payload_b64"], validate=True).decode("utf-8"))
    expected_signature = hmac.new(
        (settings.MESH_RELAY_SIGNING_KEY or settings.SECRET_KEY).encode("utf-8"),
        relay_packet["payload_b64"].encode("utf-8"),
        "sha256",
    ).hexdigest()

    assert decoded["i"] == str(incident.id)
    assert hmac.compare_digest(expected_signature, relay_packet["signature"])
