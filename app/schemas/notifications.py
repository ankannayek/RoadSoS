from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DeviceTokenUpdate(BaseModel):
    token: str = Field(..., min_length=10, max_length=4096)
    platform: str = Field(default="unknown", pattern="^(android|ios|web|unknown)$")
    device_id: Optional[str] = Field(default=None, max_length=120)


class DeviceTokenResponse(BaseModel):
    status: str
    tokens_registered: int
