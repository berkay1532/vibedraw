# v2 — Plan Üzeri Kuvvetli Akım Tasarımı

**Tarih:** 2026-06-07
**Durum:** Onaylandı
**Önceki:** v1 prototip ([2026-06-07-elektrik-projesi-pipeline-design.md](2026-06-07-elektrik-projesi-pipeline-design.md)) — DXF-in/DXF-out, etiket-merkezli, 28 test geçti.
**Referans hedef:** `ornekler/correct_output.dxf` (gerçek profesyonel proje).

---

## 1. Amaç

v1, etiket-merkezli kaba bir çıktı veriyordu. v2, `correct_output.dxf`'e yaklaşan, **gerçek oda geometrisine ve kapı konumuna dayalı** plan üzeri kuvvetli akım çizimi üretir. Kullanıcının verdiği mühendislik kurallarını uygular.

## 2. Kapsam

### Dahil (v2)
- Hedef: tek konut katı (KAT 2), plan üzeri **kuvvetli akım**.
- Aydınlatma, priz, anahtar, **buat**, **sigorta kutusu (pano)**, beyaz eşya.
- Duvarlardan **oda poligonu** çıkarımı + **kapı tespiti**.
- **Duvar kenarı linye routing**.

### Hariç (v3+)
- Pano/kolon şeması (PANO layer şeması), yük hesap tabloları.
- Zayıf akım sistemi (TV/RG6, data/CAT6, fiber/FO, diyafon, zil).
- Çok katlı/çok daireli işleme.
- Gerçek "duvar ağında en kısa yol" routing (v2'de duvara-yapışık ortogonal yaklaşımı; shortest-path sonraki adım).

## 3. Kullanıcı Mühendislik Kuralları (correct_output ile doğrulandı)

1. **Linyeler duvar içinden geçmez, duvar kenarından gider.**
2. **Priz ve anahtarlar oda içinde, kapı girişinin hemen yanında.**
3. **Aydınlatma oda merkezinde, 1 adet.**
4. **Sigorta kutusu (pano) var; tüm linyeler ondan çıkar.**
5. **Her beyaz eşya için ayrı linye.**
6. **Linye grupları:** 1 aydınlatma + 1 priz (beyaz eşya hariç) + N beyaz eşya.
   - **Düzeltme (correct_output'tan):** Anahtar ayrı linye DEĞİL. Aydınlatma linyesinin parçası: PANO → aydınlatma linyesi → **buat** → armatür + anahtar (anahtar armatürü kumanda eder). Kullanıcı bunu onayladı.

### Linye topolojisi
```
PANO ──aydınlatma linyesi──► BUAT ──► armatür + anahtar     (1 linye)
PANO ──priz linyesi────────► prizler (beyaz eşya hariç)      (1 linye)
PANO ──beyaz eşya linyesi──► her beyaz eşya ayrı             (N linye)
```

### Beyaz eşya
Mimari altlıkta çizili değil → **kural ile standart konuma** yerleştirilir (mutfak tezgah duvarı: fırın/bulaşık; ıslak hacim: çamaşır; kombi mutfak/banyo duvarı).

## 4. Mimari

v1 iskeleti korunur: LangGraph ince kabuk + saf framework-bağımsız `core/` aşamaları, deterministik kurallar, LLM yalnızca isim normalize + açıklama (sayı üretmez). Yeni aşamalar mevcut pipeline'a eklenir.

**Yeni veri:** `Room.polygon` (oda sınırı), `Room.center` (temsilî iç nokta), `Door` (konum + ait olduğu oda), `Symbol.kind` genişler ("light","socket","switch","junction","panel","appliance"), `Appliance` (beyaz eşya).

## 5. Geometri Temeli — Yöntem (M1)

**Raster flood-fill** (polygonize değil — duvarlar parçalı/boşluklu, doğrulandı):
1. Hedef katın sınır kutusu (bbox) hesaplanır.
2. Duvar layer'ları (`duv`, `PislikMimar.com - duvar`, `.ABM-DUVAR`, `ince`) + **kapı kanadı** (`kapi`,`.KAPI`,`.ABM-KAPI`) bir raster ızgaraya çizilir (kapı render edilince kapı boşluğu kapanır → flood-fill sızmaz).
3. Her oda etiketi noktasından **BFS flood-fill** → oda iç maskesi.
4. Maskeden: temsilî merkez (centroid/iç nokta) + **sınır poligonu** (Moore sınır izleme + sadeleştirme).
5. Sızma kontrolü: maske alanı bbox'ın aşırı büyük oranıysa hata/uyarı.

**Kapı tespiti:** kapı layer'larındaki entity'lerden kapı konumları; her kapı en yakın oda(lar)la ilişkilendirilir. Cihaz yerleşiminde "kapı yanı" referansı olur.

**Bağımlılık:** `numpy` (raster + flood-fill), `shapely` (poligon sadeleştirme/işlem). Mümkünse harici contour kütüphanesi olmadan elde edilir.

## 6. Kilometre Taşları

| Milestone | İçerik | Doğrulama (programatik) |
|---|---|---|
| **M1 — Geometri temeli** | Oda poligonu (flood-fill) + merkez + containment + kapı tespiti | Her oda merkezi kendi maskesinin içinde; poligon alanı ~ "A: m²" ile tutarlı; KAT2 odaları ayrı maskeler |
| **M2 — Cihaz yerleşimi** | Aydınlatma merkezde 1; anahtar+priz kapı yanında oda içinde; buatlar; beyaz eşya standart konum | Her sembol doğru odanın maskesi içinde; armatür merkeze yakın; anahtar/priz kapıya yakın |
| **M3 — Linye + pano** | Pano girişe; aydınlatma/priz/beyaz eşya linyeleri; duvar kenarı routing | Linye noktaları duvar pikseli üzerinden geçmiyor; tüm linyeler panodan başlıyor |

## 7. Çıktı

`output/elektrik.dxf` — mimari altlık korunur, elektrik yeni `EL-*` layer'larına eklenir (aydınlatma, priz, anahtar, buat, linye, pano, beyaz eşya, oda-sınırı [debug]). AutoCAD'de açılıp görsel doğrulanır.

## 8. Riskler

- **Flood-fill sızması:** kapı/duvar boşlukları kapanmazsa odalar birleşir. Mitigasyon: duvar dilatasyonu + kapı render + sızma alan kontrolü.
- **Raster çözünürlüğü:** poligon kenarları piksel kaba; sadeleştirme ile düzeltilir, mühendislik için yeterli.
- **Routing kalitesi:** v2 duvara-yapışık ortogonal; profesyonel shortest-path değil. Bilinçli kademeleme.
- **Beyaz eşya konumu:** kural-tabanlı yaklaşık; gerçek mutfak yerleşimi değil.
