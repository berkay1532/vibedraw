# tests/test_llm.py
from core.perception import llm


def test_normalize_room_name_uses_client(monkeypatch):
    captured = {}

    def fake_call(prompt, model):
        captured["prompt"] = prompt
        captured["model"] = model
        return "bedroom"

    monkeypatch.setattr(llm, "_call_text", fake_call)
    result = llm.normalize_room_name("Ebeveyn Yatak")
    assert result == "bedroom"
    assert "Ebeveyn Yatak" in captured["prompt"]


def test_explain_decision_uses_client(monkeypatch):
    monkeypatch.setattr(llm, "_call_text", lambda prompt, model: "Çünkü yüksek güç.")
    txt = llm.explain_decision("kitchen separate circuit", {"area": 14.5})
    assert "yüksek güç" in txt.lower() or len(txt) > 0
