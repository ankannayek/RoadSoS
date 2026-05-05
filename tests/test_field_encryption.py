from app.services.field_encryption import FieldEncryption


def test_field_encryption_dev_plain_roundtrip(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "FIELD_ENCRYPTION_KEYS", None)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    service = FieldEncryption()

    key_id, payload = service.encrypt_json({"blood_group": "O+", "emergency_contacts": [{"name": "A", "phone": "112"}]})

    assert key_id == "plain-dev"
    assert service.decrypt_json(payload)["blood_group"] == "O+"


def test_field_encryption_fernet_roundtrip(monkeypatch):
    from app.core.config import settings

    key = FieldEncryption.generate_key()
    monkeypatch.setattr(settings, "FIELD_ENCRYPTION_KEYS", f"v1:{key}")
    service = FieldEncryption()

    key_id, payload = service.encrypt_json({"allergies": "penicillin"})

    assert key_id == "v1"
    assert payload.startswith("fernet:v1:")
    assert service.decrypt_json(payload)["allergies"] == "penicillin"
