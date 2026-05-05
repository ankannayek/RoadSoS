from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings


@dataclass(frozen=True)
class EncryptionKeyset:
    active_key_id: str
    fernet: MultiFernet


class FieldEncryption:
    """Small envelope encryption wrapper for medical/contact payloads.

    Local development can boot without keys and stores `plain:` payloads. In
    production, startup validation requires FIELD_ENCRYPTION_KEYS, so sensitive
    fields are encrypted before persistence.
    """

    def __init__(self) -> None:
        self._keyset = self._load_keys(settings.FIELD_ENCRYPTION_KEYS)

    @staticmethod
    def _load_keys(raw: str | None) -> EncryptionKeyset | None:
        if not raw:
            return None
        entries = [entry.strip() for entry in raw.split(",") if entry.strip()]
        key_pairs: list[tuple[str, Fernet]] = []
        for entry in entries:
            if ":" not in entry:
                raise RuntimeError("FIELD_ENCRYPTION_KEYS entries must use key-id:fernet-key format")
            key_id, key = entry.split(":", 1)
            Fernet(key.encode("utf-8"))
            key_pairs.append((key_id.strip(), Fernet(key.encode("utf-8"))))
        if not key_pairs:
            return None
        return EncryptionKeyset(active_key_id=key_pairs[0][0], fernet=MultiFernet([pair[1] for pair in key_pairs]))

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode("utf-8")

    def encrypt_json(self, payload: dict[str, Any]) -> tuple[str, str]:
        normalized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        if not self._keyset:
            if settings.is_production and settings.FIELD_ENCRYPTION_REQUIRED_IN_PRODUCTION:
                raise RuntimeError("FIELD_ENCRYPTION_KEYS is required in production")
            return "plain-dev", "plain:" + base64.urlsafe_b64encode(normalized.encode("utf-8")).decode("ascii")
        token = self._keyset.fernet.encrypt(normalized.encode("utf-8")).decode("utf-8")
        return self._keyset.active_key_id, f"fernet:{self._keyset.active_key_id}:{token}"

    def decrypt_json(self, encrypted_payload: str | None) -> dict[str, Any]:
        if not encrypted_payload:
            return {}
        if encrypted_payload.startswith("plain:"):
            raw = base64.urlsafe_b64decode(encrypted_payload.removeprefix("plain:").encode("ascii")).decode("utf-8")
            return json.loads(raw)
        if encrypted_payload.startswith("fernet:"):
            if not self._keyset:
                raise RuntimeError("FIELD_ENCRYPTION_KEYS is required to decrypt private profile data")
            parts = encrypted_payload.split(":", 2)
            if len(parts) != 3:
                raise RuntimeError("Invalid encrypted private profile payload")
            try:
                raw = self._keyset.fernet.decrypt(parts[2].encode("utf-8")).decode("utf-8")
            except InvalidToken as exc:
                raise RuntimeError("Unable to decrypt private profile payload") from exc
            return json.loads(raw)
        raise RuntimeError("Unsupported private profile payload format")


field_encryption = FieldEncryption()
