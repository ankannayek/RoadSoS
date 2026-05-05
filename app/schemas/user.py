from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class EmergencyContact(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=5, max_length=20)
    relation: Optional[str] = Field(default=None, max_length=60)
    notify_on_sos: bool = True


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=5, max_length=20)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=8, max_length=128)
    blood_group: Optional[str] = Field(default=None, max_length=10)
    medical_conditions: Optional[str] = Field(default=None, max_length=500)
    allergies: Optional[str] = Field(default=None, max_length=300)
    emergency_contacts: List[EmergencyContact] = Field(default_factory=list)
    preferred_language: str = Field(default="en", max_length=12)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        normalized = value.strip().replace(" ", "")
        if len(normalized) < 5:
            raise ValueError("Phone number is too short")
        return normalized


class UserLogin(BaseModel):
    phone: str = Field(..., min_length=5, max_length=20)
    password: str = Field(..., min_length=1, max_length=128)


class AdminBootstrapRequest(BaseModel):
    phone: str = Field(..., min_length=5, max_length=20)
    bootstrap_token: str = Field(..., min_length=48, max_length=512)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    blood_group: Optional[str] = Field(default=None, max_length=10)
    medical_conditions: Optional[str] = Field(default=None, max_length=500)
    allergies: Optional[str] = Field(default=None, max_length=300)
    emergency_contacts: Optional[List[EmergencyContact]] = None
    preferred_language: Optional[str] = Field(default=None, max_length=12)


class UserOut(BaseModel):
    id: UUID
    name: str
    phone: str
    email: Optional[EmailStr] = None
    blood_group: Optional[str] = None
    medical_conditions: Optional[str] = None
    allergies: Optional[str] = None
    emergency_contacts: Optional[List[EmergencyContact]] = None
    preferred_language: str = "en"
    role: str = "user"

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserOut
