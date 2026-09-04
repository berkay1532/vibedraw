# Elektrik Projesi Pipeline — Tasarım (v1 Feasibility Prototipi)

**Tarih:** 2026-06-07
**Durum:** Onay bekliyor
**Hedef:** Mimari altlıktan (DXF) tek konut katı için aydınlatma + priz elektrik projesi üreten, uçtan uca çalışan deterministik pipeline prototipi.

---

## 1. Amaç ve Başarı Kriteri

Bu çalışmanın amacı **feasibility (yapılabilirlik) kanıtıdır**. "Bu iş olur mu?" sorusunu en hızlı şekilde cevaplamak için çirkin ama uçtan uca çalışan bir iskelet kurulur.

**v1 başarılı sayılır eğer:**
- Bir DXF mimari altlık girdi olarak alınır,
- Tek bir konut katı (örnek dosyada KAT 2) için odalar otomatik tanınır,
- Her odaya deterministik kurallarla aydınlatma + priz sembolleri ve linye bağlantıları atanır,
- Sonuç, mimari altlığa dokunmadan yeni layer'lara çizilmiş bir DXF olarak yazılır,
- Bu DXF AutoCAD'de açılıp DWG olarak kaydedilebilir.

## 2. Kapsam

### Dahil (v1)
- **Girdi:** DXF (operatör DWG→DXF dönüşümünü AutoCAD/CloudConvert ile yapar)
- **Hedef:** Tek konut katı — örnek dosyadaki KAT 2 (Salon, Mutfak, Yatak Odası, Banyo, Hol, Kat Holü, Balkon)
- **Üretilen:** Aydınlatma sortileri + priz sortileri + linye bağlantıları
- **Yerleşim:** Etiket-merkezli (sembol oda etiketi noktası çevresine konur)
- **Çıktı:** DXF (yeni elektrik layer'larıyla)
- **Orkestrasyon:** LangGraph (ince kabuk) + framework-bağımsız saf aşama fonksiyonları
- **LLM:** Baştan aktif (bilinmeyen oda ismi normalizasyonu + karar gerekçesi metni)

### Hariç (bilinçli YAGNI — v2+)
- DWG'yi doğrudan okuma/yazma (insana/AutoCAD'e bırakıldı)
- Duvarlardan tam oda-sınırı poligonu inşası (shapely ile, v2)
- Duvar-temelli düzgün sembol yerleşimi ve profesyonel kablo routing
- Kuvvet, zayıf akım, topraklama, pano şeması, yükselme/kolon hattı
- Çok katlı / çok daireli bütün bina işleme
- Yönetmelik QA katmanının tam kapsamı (v1'de temel kontroller)

## 3. Mimari

### 3.1. Temel İlkeler (değişmez)
1. **Orkestratör = deterministik state machine**, ajan sürüsü değil. Akış sabit ve sıralıdır.
2. **Mühendislik kararları deterministik.** Kablo kesiti, sigorta, linye sayısı, priz/armatür adedi → kodlanmış kural motorundan gelir. **LLM asla sayı/karar üretmez.**
3. **LLM yalnızca yardımcı:** belirsiz oda ismini standart tipe eşleme + kararların insan-diline çevrilmesi (gerekçe metni).
4. **Aşamalar saf ve framework-bağımsız.** LangGraph yalnızca kablolama kabuğudur; mühendislik mantığı LangGraph'e gömülmez. Her aşama LangGraph olmadan çağrılabilir ve test edilebilir.

### 3.2. Akış

```
DXF → [1.Parse] → [2.Mahallendirme] → [3.Karar Motoru] → [4.Yerleşim] → [5.DXF Üretim] → DXF
                         ↑                      ↑
                   (LLM: bilinmeyen      (LLM: gerekçe metni;
                    isim normalize)       sayı ÜRETMEZ)
```

Her aşama arasında **doğrulama (validation)** çalışır; kontrat ihlali olursa pipeline durur ve net hata raporu verir (sessizce yanlış çizim üretmez).

### 3.3. Kod Yapısı
```
core/
  ir.py          # Veri modelleri (BuildingIR, DesignIR)
  stages.py      # Saf aşama fonksiyonları (LangGraph'siz çalışır)
  rules/         # Kural tabloları (YAML) + kural motoru
  llm.py         # İnce LLM arayüzü (test'te mock'lanabilir)
  validate.py    # Aşamalar arası doğrulama
graph.py         # LangGraph kablolama (node'lar = stages sarmalayıcıları)
symbols/         # Sembol kütüphanesi (blok tanımları)
ornekler/        # Örnek girdi DXF
output/          # Üretilen DXF
tests/           # Aşama bazlı unit testler (sentetik DXF'lerle)
```

## 4. Aşamalar ve Kontratları

### Aşama 1 — Parse & Normalize *(deterministik)*
- `ezdxf` ile DXF oku.
- `YAZI` layer'ındaki MTEXT/TEXT'leri çıkar; MTEXT format kodlarını temizle (`{\fArial...;METIN}` → `METIN`).
- İsim metinlerini alan metinlerinden ayır (`A: ...m²` deseni alandır).
- Her isim, en yakın alan metniyle eşleştirilir (nearest-neighbor).
- Katlar x-ekseni boşluğuna göre kümelenir; hedef kat (KAT 2) seçilir.
- **Çıktı:** `BuildingIR { floors: [ { rooms: [ {raw_name, area_m2, label_xy} ] } ] }`

### Aşama 2 — Mahallendirme *(deterministik + LLM)*
- Ham oda ismini kanonik tipe eşle (sözlük): "Yatak Odası"→`bedroom`, "Salon"→`living`, "Mutfak"→`kitchen`, "Banyo"→`bathroom`, "WC"→`wc`, "Hol"/"Kat Holü"→`circulation`, "Balkon"→`balcony`...
- Sözlükte olmayan isim çıkarsa → **LLM çağrısı**: "bu oda ismi hangi standart tipe girer?" (Haiku).
- **Çıktı:** `BuildingIR` (her odada `room_type` dolu).

### Aşama 3 — Mühendislik Karar Motoru *(deterministik kural motoru — KALP)*
- Her `room_type` + `area_m2` için kurallar uygulanır:
  - Kaç aydınlatma sortisi (örn. alan başına / oda tipine göre asgari adet),
  - Kaç priz sortisi,
  - Hangi linyeye bağlanır (örn. mutfak/banyo ayrı linye).
- Kurallar **YAML kural tablosunda** kodlanır; Elektrik İç Tesisleri Yönetmeliği temelli, başta basit ve genişletilebilir.
- **LLM sayı üretmez**; yalnızca uygulanan kuralın **gerekçe metnini** üretir (Sonnet, opsiyonel).
- **Çıktı:** `DesignIR { rooms: [ {fixtures: [...], sockets: [...], circuit_id} ], circuits: [...] }`

### Aşama 4 — Yerleşim *(deterministik, basit)*
- Tavan armatürü → oda etiketi noktası (≈oda merkezi).
- Prizler → etiket çevresine sabit ofsetlerle dağıtılır.
- Linye → semboller arası basit polyline.
- **Çıktı:** `DesignIR` (her sembolde `xy` konumu dolu).

### Aşama 5 — DXF Üretim *(deterministik)*
- `ezdxf` ile **yeni layer'lara** (örn. `EL-AYDINLATMA`, `EL-PRIZ`, `EL-LINYE`) semboller ve çizgiler eklenir; **mimari altlık değiştirilmez**.
- Sembol kütüphanesi: basit bloklar (armatür, priz, vb.).
- Sonuç `output/` altına yazılır.

## 5. Veri Modeli (IR)

İki ana yapı, aşamalar arasında akar:
- **`BuildingIR`** — geometriden çıkarılan ham + anlamlandırılmış yapı (katlar, odalar, tipler, alanlar, etiket konumları).
- **`DesignIR`** — mühendislik kararları sonrası (semboller, linyeler, konumlar, gerekçeler).

Net ayrım: `BuildingIR` "ne var" (girdi gerçeği), `DesignIR` "ne ekleyeceğiz" (mühendislik çıktısı).

## 6. LLM Arayüzü

- Tek ince modül (`core/llm.py`) arkasında; testlerde **mock'lanabilir**.
- İki fonksiyon: `normalize_room_name(raw)` → kanonik tip; `explain_decision(rule, context)` → gerekçe metni.
- Model: normalize için Haiku 4.5, gerekçe için Sonnet 4.6 (gözden geçirilebilir).
- `ANTHROPIC_API_KEY` `.env` üzerinden.
- **Güvenlik sınırı:** LLM çıktısı asla mühendislik sayısına dönüşmez; yalnızca tip-eşleme ve metin.

## 7. Doğrulama ve Hata Yönetimi

- Her aşama çıktısı bir sonrakine verilmeden önce kontrat doğrulaması geçer (örn. her odanın tipi var mı, her sembolün linyesi var mı, her sembolün konumu var mı).
- İhlalde pipeline **durur** ve hangi aşamada ne eksik olduğunu söyler. Sessiz/yanlış çizim üretmek yasak.

## 8. Teknoloji

- **Python 3** (ezdxf'in olgunluğu, LangGraph, LLM SDK ve geometri kütüphaneleri — shapely/networkx/numpy — hepsi Python'da olduğu için kesin tercih).
- **ezdxf** — DXF oku/yaz (tek ağır bağımlılık).
- **LangGraph** — orkestrasyon kabuğu.
- **anthropic** SDK — LLM çağrıları.
- **PyYAML** — kural tabloları.
- Test: `pytest`, küçük sentetik DXF'lerle aşama-bazlı.

## 9. Örnek Dosyadan Doğrulanan Gerçekler

`ornekler/empty-structure.dxf` (R2010) incelemesiyle teyit edildi:
- Oda **isimleri** `YAZI` layer'ında MTEXT olarak var (Salon, Mutfak, Yatak Odası, Banyo, Hol, WC, Balkon, Kat Holü, Ofis, Merdiven).
- Oda **alanları** hazır (`A: 14.12m²` formatında) — hesaplamaya gerek yok, okunuyor.
- İsim↔alan eşleşmesi nearest-neighbor ile kusursuz çalışıyor (mesafeler ~4-8 birim).
- Dosyada **yan yana 3 kat planı** var; x-boşluğuna göre temiz kümeleniyor (KAT 1 ofis/zemin, KAT 2 konut, KAT 3 teras çatı).
- **Odalar kapalı poligon DEĞİL** — 19 etiketin 17'sini kapsayan oda-sınırı poligonu yok. Bu yüzden tam poligon inşası v2'ye ertelendi; v1 etiket-merkezli yerleşim kullanır.

## 10. Riskler ve Açık Konular

- **Girdi çeşitliliği:** Farklı bürolardan gelen DXF'lerde layer/blok/isim standardı değişebilir. v1 temiz örneğe odaklanır; normalizasyon dayanıklılığı ileride artırılır.
- **Etiket-merkezli yerleşim** mükemmel değil (sembol oda dışına/duvara denk gelebilir). Feasibility için kabul; v2'de duvar-temelli yerleşim.
- **Kural tablosunun doğruluğu** asıl katma değer; başta basit, mühendis onayıyla derinleştirilecek.
- **Çıktı kalitesi** prototip seviyesinde; mühendis gözüyle revizyon beklenir (insan onayı adımı v1 dışında ama mimaride yeri var).
