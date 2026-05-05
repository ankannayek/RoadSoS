from __future__ import annotations

<<<<<<< HEAD
import secrets

=======
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
<<<<<<< HEAD
from app.schemas.user import AdminBootstrapRequest, TokenResponse, UserCreate, UserLogin
from app.services.private_profile import build_user_out, load_private_profile, upsert_private_profile
=======
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserOut
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    existing_phone = await db.execute(select(User).where(User.phone == payload.phone))
    if existing_phone.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Phone already registered")
    if payload.email:
        existing_email = await db.execute(select(User).where(User.email == payload.email))
        if existing_email.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        name=payload.name,
        phone=payload.phone,
        email=str(payload.email) if payload.email else None,
        hashed_password=get_password_hash(payload.password),
<<<<<<< HEAD
        preferred_language=payload.preferred_language,
    )
    db.add(user)
    await db.flush()
    await upsert_private_profile(
        db,
        user,
        {
            "blood_group": payload.blood_group,
            "medical_conditions": payload.medical_conditions,
            "allergies": payload.allergies,
            "emergency_contacts": [contact.model_dump() for contact in payload.emergency_contacts],
        },
    )
    await db.commit()
    await db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    private_profile = await load_private_profile(db, user)
    return TokenResponse(access_token=token, expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES, user=build_user_out(user, private_profile))
=======
        blood_group=payload.blood_group,
        medical_conditions=payload.medical_conditions,
        allergies=payload.allergies,
        emergency_contacts=[contact.model_dump() for contact in payload.emergency_contacts],
        preferred_language=payload.preferred_language,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token, expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES, user=UserOut.model_validate(user))
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.phone == credentials.phone, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id)})
<<<<<<< HEAD
    private_profile = await load_private_profile(db, user)
    return TokenResponse(access_token=token, expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES, user=build_user_out(user, private_profile))


@router.post("/bootstrap-admin")
async def bootstrap_admin(payload: AdminBootstrapRequest, db: AsyncSession = Depends(get_db)):
    if not settings.ADMIN_BOOTSTRAP_ENABLED:
        raise HTTPException(status_code=404, detail="Admin bootstrap is disabled")
    if not settings.ADMIN_BOOTSTRAP_TOKEN or not secrets.compare_digest(payload.bootstrap_token, settings.ADMIN_BOOTSTRAP_TOKEN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bootstrap token")

    existing_admin = await db.execute(select(User.id).where(User.role == "admin", User.is_active.is_(True)).limit(1))
    if existing_admin.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Admin bootstrap is already closed")

    result = await db.execute(select(User).where(User.phone == payload.phone, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = "admin"
    await db.commit()
    return {"status": "promoted", "user_id": str(user.id), "role": user.role}
=======
    return TokenResponse(access_token=token, expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES, user=UserOut.model_validate(user))
>>>>>>> d4f78981cc38ff26fade88ca9eda8ea4ce1befd0
