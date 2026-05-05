import base64
import json
import pytest

def test_golden_hour_risk_index():
    from app.api.bundle import _calculate_golden_hour_risk
    
    # Critical near
    assert _calculate_golden_hour_risk("P1_CRITICAL", 2.0) == 0.99
    # Critical far
    assert _calculate_golden_hour_risk("P1_CRITICAL", 20.0) == 1.00 # Max 1.0
    
    # Medium near
    assert _calculate_golden_hour_risk("P3_MEDIUM", 5.0) == 0.50
    

def test_mesh_relay_signature_verification():
    from app.core.config import settings
    import hmac
    import hashlib
    
    payload_b64 = base64.b64encode(json.dumps({"i": "test", "l": [0,0], "p": "P1_CRITICAL"}).encode('utf-8')).decode('utf-8')
    
    # Valid sig
    valid_sig = hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    assert hmac.compare_digest(valid_sig, valid_sig) is True
    assert hmac.compare_digest(valid_sig, "fake_sig") is False
