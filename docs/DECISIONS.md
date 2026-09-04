# Kararlar ve adaylar

Biçim: **[karar|aday] tarih — başlık** · ne · neden · alternatif. "Aday" = görülen ama
uygulanmayan iyileştirme fikri; uygulanınca "karar" olur ve commit'i yazılır.

## Kararlar

- **[karar] 2026-09-04 — v1 IR'ın perception/elektrik bölünmesi (Adım 1).**
  `core/ir.py` ikiye ayrıldı: `core/perception/ir.py` (Room, Door, Floor, BuildingIR — perception
  sahibi) ve `core/electrical/ir.py` (Device, Symbol, RoomDesign, Circuit, DesignIR — Room'u
  perception'dan import eder). Neden: plan "ir.py electrical'a taşınır" diyor ama perception
  kodu Room/Floor/BuildingIR'a bağımlı; perception elektrikten import edemez (ARCHITECTURE §0).
  Alanlar ve mantık birebir korundu; `Floor.devices` şimdilik tipsiz liste olarak perception
  Floor'unda kaldı (aşağıdaki aday). Alternatif: tek dosyayı electrical'a taşıyıp perception'ı
  ona bağlamak — bağımlılık yönü ters olurdu.

## Adaylar (uygulanmadı)

- **[aday] 2026-09-04 — `Floor.devices` perception IR'dan çıksın.** Elektrik alanı; Adım 2'de
  v2 IR yazılırken elektrik motoru kendi Floor görünümünü türetmeli.
- **[aday] 2026-09-04 — `core/validate.py` electrical'a taşınsın.** `validate_design` DesignIR
  doğruluyor; `validate_building` perception'a ait. Plan listelemediği için Adım 1'de kökte
  bırakıldı, importları güncellendi.
- **[aday] 2026-09-04 — `evaluate.py`, `triage_dataset.py`, `annotate.py` → `experiments/`.**
  ARCHITECTURE §10 hedef yapıda orada; Adım 0 kapsamı dışı olduğu için taşınmadı.
- **[aday] 2026-09-04 — `run_baseline.run_one` içindeki akış (etiket → ölçek → kat seçimi →
  reconstruct) `pipeline.py`'ye taşınsın.** Adım 4'te planlı.
- **[aday] 2026-09-04 — `core/sheets.py` çıktısı (görünümler, kat adları) runner'ın kat
  seçimine bağlansın; tek kat yerine tüm kat planları çıksın.** Pafta anlama v1 hazır ama
  bağlı değil.
