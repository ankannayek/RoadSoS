from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from jose import jwt
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.incident import IncidentResponderAttempt
from app.models.notification import NotificationLog
from app.models.user import User

logger = logging.getLogger(__name__)
# Fixed Google endpoint, not a secret.
GOOGLE_OAUTH_TOKEN_URI = "https://oauth2.googleapis.com/token"  # nosec B105


def _uuid_or_none(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _compact_message(payload: Dict[str, Any]) -> str:
    lat = payload.get("lat")
    lng = payload.get("lng")
    maps = f" https://maps.google.com/?q={lat},{lng}" if lat is not None and lng is not None else ""
    priority = payload.get("priority", "SOS")
    incident_id = payload.get("incident_id", "")
    desc = str(payload.get("description", ""))[:120]
    return f"RoadSoS {priority}: incident {incident_id}.{maps} {desc}".strip()


class NotificationHub:
    """Central notification facade for FCM push, Twilio SMS, and dashboard events.

    Uses a shared httpx.AsyncClient for connection pooling and avoids creating
    a new TCP+TLS connection per notification (critical during P1 escalation
    where 40+ notifications fire in sequence).
    """

    def __init__(self) -> None:
        self._fcm_oauth_token: str | None = None
        self._fcm_token_expires_at: float = 0
        self._http_client: httpx.AsyncClient | None = None

    def _get_http_client(self) -> httpx.AsyncClient:
        """Lazily create a shared httpx client with connection pooling."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=10,
                limits=httpx.Limits(
                    max_connections=50,
                    max_keepalive_connections=20,
                    keepalive_expiry=120,
                ),
            )
        return self._http_client

    async def close(self) -> None:
        """Shutdown the shared HTTP client. Called during app lifespan teardown."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def _log(
        self,
        db: AsyncSession,
        incident_id: str | None,
        recipient_type: str,
        recipient: str | None,
        channel: str,
        status: str,
        payload: Dict[str, Any],
        provider_message_id: str | None = None,
        error: str | None = None,
    ) -> None:
        await db.execute(
            insert(NotificationLog).values(
                incident_id=_uuid_or_none(incident_id),
                recipient_type=recipient_type,
                recipient=recipient,
                channel=channel,
                status=status,
                provider_message_id=provider_message_id,
                payload=payload,
                error=error,
            )
        )

    async def _log_attempt(
        self,
        db: AsyncSession,
        incident_id: str | None,
        responder_type: str,
        responder_id: Any,
        channel: str,
        tier: str,
        status: str,
        payload: Dict[str, Any],
    ) -> None:
        await db.execute(
            insert(IncidentResponderAttempt).values(
                incident_id=_uuid_or_none(incident_id),
                responder_type=responder_type,
                responder_id=_uuid_or_none(str(responder_id)) if responder_id else None,
                channel=channel,
                tier=tier,
                status=status,
                payload=payload,
            )
        )

    @staticmethod
    def _load_fcm_service_account() -> dict[str, Any] | None:
        raw = settings.FCM_SERVICE_ACCOUNT_JSON
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            try:
                return json.loads(base64.b64decode(raw, validate=True).decode("utf-8"))
            except Exception as exc:
                raise RuntimeError("FCM_SERVICE_ACCOUNT_JSON must be raw JSON or base64 encoded JSON") from exc

    async def _get_fcm_oauth_token(self) -> tuple[str | None, str | None]:
        if self._fcm_oauth_token and time.time() < self._fcm_token_expires_at - 60:
            return self._fcm_oauth_token, None
        service_account = self._load_fcm_service_account()
        if not settings.FCM_PROJECT_ID or not service_account:
            return None, "FCM_PROJECT_ID/FCM_SERVICE_ACCOUNT_JSON not configured"

        now = int(time.time())
        token_uri = service_account.get("token_uri") or GOOGLE_OAUTH_TOKEN_URI
        if token_uri != GOOGLE_OAUTH_TOKEN_URI:
            raise RuntimeError(f"FCM token_uri must be {GOOGLE_OAUTH_TOKEN_URI}")
        claims = {
            "iss": service_account["client_email"],
            "scope": "https://www.googleapis.com/auth/firebase.messaging",
            "aud": token_uri,
            "iat": now,
            "exp": now + 3600,
        }
        assertion = jwt.encode(claims, service_account["private_key"], algorithm="RS256")
        data = {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}
        client = self._get_http_client()
        response = await client.post(token_uri, data=data)
        response.raise_for_status()
        body = response.json()
        self._fcm_oauth_token = body["access_token"]
        self._fcm_token_expires_at = time.time() + int(body.get("expires_in", 3600))
        return self._fcm_oauth_token, None

    async def _send_fcm(self, token: str, payload: Dict[str, Any]) -> tuple[str, str | None, str | None]:
        try:
            access_token, token_error = await self._get_fcm_oauth_token()
        except Exception as exc:
            return "failed", None, str(exc)[:1000]
        if not access_token:
            return "skipped_config_missing", None, token_error or "FCM service account not configured"
        url = f"https://fcm.googleapis.com/v1/projects/{settings.FCM_PROJECT_ID}/messages:send"

        is_silent = payload.get("silent", False)

        # For silent SOS, send a data-only FCM message (no visible notification).
        # This prevents an aggressor from seeing an alert on the victim's phone.
        if is_silent:
            body = {
                "message": {
                    "token": token,
                    "data": {k: str(v) for k, v in payload.items() if v is not None},
                    "android": {"priority": "HIGH"},
                    "apns": {
                        "headers": {"apns-priority": "10"},
                        "payload": {
                            "aps": {"content-available": 1, "sound": ""},
                        },
                    },
                }
            }
        else:
            body = {
                "message": {
                    "token": token,
                    "notification": {
                        "title": "RoadSoS Emergency Alert",
                        "body": _compact_message(payload)[:240],
                    },
                    "data": {k: str(v) for k, v in payload.items() if v is not None},
                    "android": {"priority": "HIGH"},
                    "apns": {"headers": {"apns-priority": "10"}},
                }
            }
        try:
            client = self._get_http_client()
            response = await client.post(url, headers={"Authorization": f"Bearer {access_token}"}, json=body)
            response.raise_for_status()
            data = response.json()
            return "sent", data.get("name"), None
        except Exception as exc:  # pragma: no cover - network/provider dependent
            return "failed", None, str(exc)[:1000]

    async def _send_sms(self, phone: str, payload: Dict[str, Any]) -> tuple[str, str | None, str | None]:
        if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER):
            return "skipped_config_missing", None, "Twilio SMS credentials not configured"
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
        data = {"From": settings.TWILIO_FROM_NUMBER, "To": phone, "Body": _compact_message(payload)}
        try:
            client = self._get_http_client()
            response = await client.post(url, data=data, auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN))
            response.raise_for_status()
            body = response.json()
            return "sent", body.get("sid"), None
        except Exception as exc:  # pragma: no cover
            return "failed", None, str(exc)[:1000]

    @staticmethod
    def _tokens_from_user(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, list):
            tokens: list[str] = []
            for item in value:
                if isinstance(item, str):
                    tokens.append(item)
                elif isinstance(item, dict) and item.get("token"):
                    tokens.append(str(item["token"]))
            return list(dict.fromkeys(tokens))
        return []

    async def notify_volunteers(self, db: AsyncSession, incident_id: str, volunteers: List[Dict[str, Any]], payload: Dict[str, Any]) -> int:
        user_ids = [v.get("user_id") for v in volunteers if v.get("user_id")]
        tokens_by_user: dict[str, list[str]] = {}
        if user_ids:
            result = await db.execute(select(User.id, User.fcm_tokens).where(User.id.in_(user_ids)))
            for row in result.all():
                tokens_by_user[str(row.id)] = self._tokens_from_user(row.fcm_tokens)

        count = 0
        for volunteer in volunteers:
            recipient = str(volunteer.get("user_id") or volunteer.get("id"))
            tokens = tokens_by_user.get(str(volunteer.get("user_id")), [])
            if not tokens:
                await self._log(db, incident_id, "volunteer", recipient, "fcm", "skipped_no_token", payload)
                await self._log_attempt(db, incident_id, "volunteer", volunteer.get("id"), "fcm", str(payload.get("tier") or "unknown"), "skipped_no_token", payload)
                continue
            for token in tokens[:3]:
                status, message_id, error = await self._send_fcm(token, payload)
                await self._log(db, incident_id, "volunteer", recipient, "fcm", status, payload, message_id, error)
                await self._log_attempt(db, incident_id, "volunteer", volunteer.get("id"), "fcm", str(payload.get("tier") or "unknown"), status, payload)
                if status == "sent":
                    count += 1
        return count

    async def notify_services(self, db: AsyncSession, incident_id: str, services: List[Dict[str, Any]], payload: Dict[str, Any]) -> int:
        count = 0
        for service in services:
            phone = service.get("phone")
            recipient = phone or str(service.get("id"))
            if phone and settings.SMS_FALLBACK_ENABLED:
                status, message_id, error = await self._send_sms(phone, payload)
                await self._log(db, incident_id, "service", phone, "sms", status, payload, message_id, error)
                await self._log_attempt(db, incident_id, "service", service.get("id"), "sms", str(payload.get("tier") or "unknown"), status, payload)
                count += 1
        return count

    async def notify_contacts(self, db: AsyncSession, incident_id: str, contacts: List[Dict[str, Any]], payload: Dict[str, Any]) -> int:
        count = 0
        for contact in contacts:
            if not contact.get("notify_on_sos", True):
                continue
            phone = contact.get("phone")
            if not phone:
                continue
            if settings.SMS_FALLBACK_ENABLED:
                sms_status, sms_id, sms_error = await self._send_sms(phone, payload)
                await self._log(db, incident_id, "contact", phone, "sms", sms_status, payload, sms_id, sms_error)
                await self._log_attempt(db, incident_id, "contact", None, "sms", str(payload.get("tier") or "unknown"), sms_status, payload)
                if sms_status == "sent":
                    count += 1
            else:
                await self._log(db, incident_id, "contact", phone, "sms", "skipped_sms_disabled", payload)
        return count


notification_hub = NotificationHub()
