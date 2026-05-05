from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.private_profile import UserPrivateProfile
from app.models.user import User
from app.schemas.user import EmergencyContact, UserOut
from app.services.field_encryption import field_encryption

PRIVATE_PROFILE_KEYS = ("blood_group", "medical_conditions", "allergies", "emergency_contacts")


def normalize_private_profile(payload: dict[str, Any]) -> dict[str, Any]:
    contacts = payload.get("emergency_contacts") or []
    normalized_contacts = [contact.model_dump() if hasattr(contact, "model_dump") else dict(contact) for contact in contacts]
    return {
        "blood_group": payload.get("blood_group"),
        "medical_conditions": payload.get("medical_conditions"),
        "allergies": payload.get("allergies"),
        "emergency_contacts": normalized_contacts,
    }


def legacy_private_profile(user: User) -> dict[str, Any]:
    return {
        "blood_group": user.blood_group,
        "medical_conditions": user.medical_conditions,
        "allergies": user.allergies,
        "emergency_contacts": user.emergency_contacts or [],
    }


async def load_private_profile(db: AsyncSession, user: User) -> dict[str, Any]:
    result = await db.execute(select(UserPrivateProfile).where(UserPrivateProfile.user_id == user.id))
    private_profile = result.scalar_one_or_none()
    if private_profile is None:
        return normalize_private_profile(legacy_private_profile(user))
    return normalize_private_profile(field_encryption.decrypt_json(private_profile.encrypted_payload))


async def upsert_private_profile(db: AsyncSession, user: User, payload: dict[str, Any]) -> UserPrivateProfile:
    normalized = normalize_private_profile(payload)
    key_id, encrypted_payload = field_encryption.encrypt_json(normalized)
    result = await db.execute(select(UserPrivateProfile).where(UserPrivateProfile.user_id == user.id))
    private_profile = result.scalar_one_or_none()
    if private_profile is None:
        private_profile = UserPrivateProfile(user_id=user.id, key_id=key_id, encrypted_payload=encrypted_payload)
        db.add(private_profile)
    else:
        private_profile.key_id = key_id
        private_profile.encrypted_payload = encrypted_payload

    # Keep legacy columns empty after the encrypted profile has been written.
    user.blood_group = None
    user.medical_conditions = None
    user.allergies = None
    user.emergency_contacts = []
    return private_profile


def build_user_out(user: User, private_profile: dict[str, Any]) -> UserOut:
    contacts = [EmergencyContact(**contact) for contact in private_profile.get("emergency_contacts") or []]
    return UserOut(
        id=user.id,
        name=user.name,
        phone=user.phone,
        email=user.email,
        blood_group=private_profile.get("blood_group"),
        medical_conditions=private_profile.get("medical_conditions"),
        allergies=private_profile.get("allergies"),
        emergency_contacts=contacts,
        preferred_language=user.preferred_language,
        role=user.role,
    )
