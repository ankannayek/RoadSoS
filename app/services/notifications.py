from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.notification import NotificationLog
from app.models.user import User

logger = logging.getLogger(__name__)


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
    """Central notification facade for FCM, WhatsApp Cloud API, Twilio SMS, and dashboard events."""

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

    async def _send_fcm(self, token: str, payload: Dict[str, Any]) -> tuple[str, str | None, str | None]:
        if not settings.FCM_PROJECT_ID or not settings.FCM_ACCESS_TOKEN:
            return "skipped_config_missing", None, "FCM_PROJECT_ID/FCM_ACCESS_TOKEN not configured"
        url = f"https://fcm.googleapis.com/v1/projects/{settings.FCM_PROJECT_ID}/messages:send"
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
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.post(url, headers={"Authorization": f"Bearer {settings.FCM_ACCESS_TOKEN}"}, json=body)
                response.raise_for_status()
                data = response.json()
                return "sent", data.get("name"), None
        except Exception as exc:  # pragma: no cover - network/provider dependent
            return "failed", None, str(exc)[:1000]

    async def _send_whatsapp(self, phone: str, payload: Dict[str, Any]) -> tuple[str, str | None, str | None]:
        if not settings.WHATSAPP_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
            return "skipped_config_missing", None, "WHATSAPP_TOKEN/WHATSAPP_PHONE_NUMBER_ID not configured"
        url = f"https://graph.facebook.com/v20.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        body = {
            "messaging_product": "whatsapp",
            "to": phone.replace("+", ""),
            "type": "text",
            "text": {"preview_url": True, "body": _compact_message(payload)},
        }
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.post(url, headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"}, json=body)
                response.raise_for_status()
                data = response.json()
                message_id = (data.get("messages") or [{}])[0].get("id")
                return "sent", message_id, None
        except Exception as exc:  # pragma: no cover
            return "failed", None, str(exc)[:1000]

    async def _send_sms(self, phone: str, payload: Dict[str, Any]) -> tuple[str, str | None, str | None]:
        if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER):
            return "skipped_config_missing", None, "Twilio SMS credentials not configured"
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
        data = {"From": settings.TWILIO_FROM_NUMBER, "To": phone, "Body": _compact_message(payload)}
        try:
            async with httpx.AsyncClient(timeout=8) as client:
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
                continue
            for token in tokens:
                status, message_id, error = await self._send_fcm(token, payload)
                await self._log(db, incident_id, "volunteer", recipient, "fcm", status, payload, message_id, error)
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
                if status == "sent":
                    count += 1
            else:
                await self._log(db, incident_id, "service", recipient, "dashboard", "queued", payload)
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
            wa_status, wa_id, wa_error = await self._send_whatsapp(phone, payload)
            await self._log(db, incident_id, "contact", phone, "whatsapp", wa_status, payload, wa_id, wa_error)
            if wa_status == "sent":
                count += 1
                continue
            if settings.SMS_FALLBACK_ENABLED:
                sms_status, sms_id, sms_error = await self._send_sms(phone, payload)
                await self._log(db, incident_id, "contact", phone, "sms", sms_status, payload, sms_id, sms_error)
                if sms_status == "sent":
                    count += 1
        return count


notification_hub = NotificationHub()
