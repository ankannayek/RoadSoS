from pathlib import Path


def test_sos_and_escalation_do_not_import_rag_or_llm():
    root = Path(__file__).resolve().parents[1]
    sos_source = (root / "app" / "api" / "sos.py").read_text(encoding="utf-8").lower()
    escalation_source = (root / "app" / "services" / "escalation.py").read_text(encoding="utf-8").lower()
    combined = sos_source + "\n" + escalation_source

    assert "services.rag" not in combined
    assert "services.llm" not in combined
    assert "gemini" not in combined
    assert "groq" not in combined
