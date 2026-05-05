from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notifications import DeviceTokenResponse, DeviceTokenUpdate
from app.schemas.user import UserOut, UserUpdate
from app.services.private_profile import PRIVATE_PROFILE_KEYS, build_user_out, load_private_profile, upsert_private_profile

router = APIRouter()


@router.get("/me", response_model=UserOut)
async def get_me(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    private_profile = await load_private_profile(db, current_user)
    return build_user_out(current_user, private_profile)


@router.patch("/me", response_model=UserOut)
async def update_me(payload: UserUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    data = payload.model_dump(exclude_unset=True)
    private_updates = {key: data.pop(key) for key in list(data.keys()) if key in PRIVATE_PROFILE_KEYS}
    if "email" in data and data["email"] is not None:
        data["email"] = str(data["email"])
    for key, value in data.items():
        setattr(current_user, key, value)
    if private_updates:
        current_private = await load_private_profile(db, current_user)
        current_private.update(private_updates)
        await upsert_private_profile(db, current_user, current_private)
    await db.commit()
    await db.refresh(current_user)
    private_profile = await load_private_profile(db, current_user)
    return build_user_out(current_user, private_profile)


@router.post("/me/device-token", response_model=DeviceTokenResponse)
async def register_device_token(payload: DeviceTokenUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    tokens = list(current_user.fcm_tokens or [])
    token_record = {
        "token": payload.token,
        "platform": payload.platform,
        "device_id": payload.device_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    tokens = [t for t in tokens if not (isinstance(t, dict) and t.get("token") == payload.token) and t != payload.token]
    tokens.append(token_record)
    current_user.fcm_tokens = tokens[-10:]
    await db.commit()
    return DeviceTokenResponse(status="registered", tokens_registered=len(current_user.fcm_tokens or []))
