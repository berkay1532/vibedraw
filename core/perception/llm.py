# core/llm.py
from __future__ import annotations
import os

MODEL_NORMALIZE = "claude-haiku-4-5-20251001"
MODEL_EXPLAIN = "claude-sonnet-4-6"

# Kanonik oda tipleri — LLM çıktısı bu kümeyle sınırlanır.
CANONICAL_TYPES = {
    "living", "kitchen", "bedroom", "bathroom", "wc",
    "circulation", "balcony", "office", "stairs", "other",
}


def _call_text(prompt: str, model: str) -> str:
    """Gerçek Anthropic çağrısı. Testlerde monkeypatch ile değiştirilir."""
    from anthropic import Anthropic

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def normalize_room_name(raw_name: str) -> str:
    """Bilinmeyen oda ismini kanonik tipe eşler. Sayı/mühendislik kararı ÜRETMEZ."""
    prompt = (
        "Aşağıdaki Türkçe oda ismini şu standart tiplerden BİRİNE eşle ve "
        "yalnızca tek kelime tip adını döndür.\n"
        f"Tipler: {', '.join(sorted(CANONICAL_TYPES))}\n"
        f"Oda ismi: {raw_name!r}\n"
        "Yanıt (tek kelime):"
    )
    result = _call_text(prompt, MODEL_NORMALIZE).strip().lower()
    return result if result in CANONICAL_TYPES else "other"


def explain_decision(rule_summary: str, context: dict) -> str:
    """Deterministik kararın insan-dili gerekçesini üretir. Kararı DEĞİŞTİRMEZ."""
    prompt = (
        "Bir elektrik mühendisliği kararının kısa (1-2 cümle) gerekçesini Türkçe yaz. "
        "Karar zaten verildi; sen yalnızca neden mantıklı olduğunu açıkla. Sayı önerme.\n"
        f"Karar: {rule_summary}\n"
        f"Bağlam: {context}\n"
    )
    return _call_text(prompt, MODEL_EXPLAIN)
