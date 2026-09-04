# core/perception/vocab.py
"""Tek sözlük: perception'daki TÜM anahtar kelime listeleri burada yaşar (CLAUDE.md "yapma listesi").

Dil-bağımsız = genel mimari kelimeler (Türkçe/İngilizce/Fransızca...), ofise özgü değil.
Ofise özgü katman ADLARI burada değildir; `source_profiles/<family>.yaml` taşır (Adım 5). Genel katman
kelimeleri (LAYER_WORDS) `names.keyword_class` ikinci kademesidir.
Adım 4: parse.ROOM_WORDS + triage.ROOM_VOCAB (birleştirildi), semantics.ROOM_DICTIONARY,
llm.CANONICAL_TYPES, windows.WINDOW_WORDS, walls._ANNO_LAYER_WORDS, sheets._KIND_WORDS/_FLOOR_WORDS
buraya taşındı; mantık değişmedi.
"""
from __future__ import annotations


def fold(s: str) -> str:
    """Türkçe güvenli casefold: İ→i, I→ı, sonra casefold. Tüm kelime eşleşmeleri bununla yapılır."""
    return ("" if s is None else str(s)).replace("İ", "i").replace("I", "ı").casefold()


def folds(s: str) -> tuple[str, str]:
    """İki katlama: Türkçe (I→ı) ve düz casefold (I→i). Büyük harfli İngilizce adlar ("WINDOW", "DIM",
    "KITCHEN") Türkçe katlamada bozulur (wındow); sözlük eşleşmesi ikisini de dener (2026-09-04 düzeltmesi)."""
    raw = "" if s is None else str(s)
    return fold(raw), raw.casefold()


def has_word(s: str, words) -> bool:
    """Kelimelerden biri metnin Türkçe ya da düz katlamasında alt-dizgi olarak geçiyor mu."""
    f1, f2 = folds(s)
    return any(w in f1 or w in f2 for w in words)


# --- Oda adları ----------------------------------------------------------------
# Alt-dizgi eşleşmesi (fold sonrası). SHORT_ROOM_WORDS tam kelime ister ("oda" ≠ "modası").
ROOM_WORDS = (
    "depo", "ofis", "çalışma odası", "sandık", "vestiyer", "giyinme", "kazan", "sığınak",
    "salon", "oturma", "mutfak", "yatak", "çocuk", "ebeveyn", "banyo", "wc",
    "tuvalet", "hol", "antre", "koridor", "balkon", "oda", "merdiven", "kiler",
    "giriş", "teras", "çamaşır", "sofa", "kat holü", "yemek", "çalışma",
    "living", "kitchen", "bedroom", "bathroom", "hall", "balcony", "corridor",
    "toilet", "dining", "entrance", "lobby",
)
SHORT_ROOM_WORDS = ("oda", "hol", "wc", "sofa")

# Oda kelimesi içerse de oda ETİKETİ olmayan yazılar ("ÇAMAŞIR MAK.YERİ", "MUTFAK DOLABI", "KAT PLANI").
NON_ROOM_WORDS = ("mak.", "makine", "makinesi", "yeri", "dolab", "dolap", "tezgah", "tezgâh", "hesab", "hesap",
                  "listesi", "tablosu", "kapısı", "penceresi", "detay", "kesit", "görünüş", "gorunus", "plan")

# Kanonik oda tipleri ve ham ad → tip eşlemesi (LLM çıktısı ROOM_TYPES ile sınırlanır).
ROOM_TYPES = frozenset({
    "living", "kitchen", "bedroom", "bathroom", "wc",
    "circulation", "balcony", "office", "stairs", "other",
})
ROOM_TYPE_MAP = {
    "salon": "living",
    "oturma odası": "living",
    "mutfak": "kitchen",
    "yatak odası": "bedroom",
    "çocuk odası": "bedroom",
    "banyo": "bathroom",
    "wc": "wc",
    "hol": "circulation",
    "kat holü": "circulation",
    "balkon": "balcony",
    "ofis": "office",
    "merdiven": "stairs",
}

# --- Açıklık / katman kelimeleri -------------------------------------------------
WINDOW_WORDS = ("pencere", "window", "glz", "glazing", "fenetre", "ventana", "cam ")

# Yazı/ölçü/aks katmanı adı ipuçları. DENENDİ ve GERİ ALINDI (walls._is_anno_layer kullanılmıyor;
# bazı export'larda "ANNO" katmanında gerçek geometri var; docs/HITL_QUESTIONS.md #3).
ANNO_LAYER_WORDS = ("yazi", "yazı", "text", "txt", "anno", "olcu", "ölçü", "dim",
                    "aks", "axis", "grid", "lejant", "legend")

# --- Pafta anlama: görünüm başlıkları ---------------------------------------------
VIEW_KIND_WORDS = {
    "floor_plan": ("kat planı", "kat plani", "planı", "plani", "plan ", "floor plan"),
    "roof_plan": ("çatı planı", "cati plani", "çatı kat", "çatı katı", "roof"),
    "section": ("kesit", "section"),
    "elevation": ("görünüş", "gorunus", "görünüm", "elevation", "cephe"),
    "site_plan": ("vaziyet", "site plan", "yerleşim"),
    "detail": ("detay", "detail", "ö: 1 / 20", "1/20", "1/10", "1/5"),
    "table": ("mahal listesi", "tablo", "liste", "hesab", "cetvel"),
}
FLOOR_WORDS = ("bodrum", "zemin", "asma", "normal kat", "tip kat", "çatı kat", "cati kat",
               "kat planı", "kat plani", ". kat", ".kat", "giriş kat", "teras kat", "bahçe kat")

# --- Katman adı sınıfları (names.keyword_class; ikinci kademe) --------------------------
# Genel, çok dilli kelimeler; ofise özgü adlar burada DEĞİL, profilde.
LAYER_WORDS = {
    "ignore": ("defpoints", "xref", "antet", "pafta", "logo", "çerçeve", "cerceve"),
    "text": ("yazi", "yazı", "text", "txt", "anno", "mahal", "etiket", "label"),
    "dim": ("olcu", "ölçü", "dim", "kot"),
    "grid": ("aks", "axis", "grid"),
    "hatch": ("tarama", "hatch", "_pat", "-pat"),
    "revision": ("revizyon", "tadilat", "revision"),
    "stair": ("merdiven", "stair", "basamak"),
    "furniture": ("tefris", "tefriş", "mobilya", "furniture", "fur", "fixt", "sanit"),
    "door": ("kapi", "kapı", "door", "porte", "puertas"),
    "window": ("pencere", "window", "cam", "glz", "glaz", "fenetre", "ventana"),
    "column": ("kolon", "column"),
    "beam": ("kiris", "kiriş", "beam"),
    "chimney": ("baca", "chimney"),
    "wall": ("duvar", "wall", "mur", "siva", "sıva", "perde"),
}


# --- Elektrik çizimi tespiti (triage) ----------------------------------------------------
# Katman adı ve blok adı ipuçları; bir dosyada toplam ELECTRICAL_MIN ve üstü isabet → verdict ELEKTRİK
# (mimari altlık değil; girdi-çıktı çifti adayı olarak raporlanır).
ELECTRICAL_LAYER_WORDS = ("elk", "elektrik", "priz", "aydinlatma", "aydınlatma", "linye", "armatür", "armatur",
                          "sigorta", "pano", "anahtar", "buat", "sorti", "kolon hatti", "kolon hattı")
ELECTRICAL_BLOCK_WORDS = ("anahtar", "buat", "priz", "armatür", "armatur", "etanj", "ayd", "sigorta", "pano", "lamba", "aplik")
