# GT (ground truth) kılavuzu

GT dosyaları `data/ground_truth/<dosya>.json`; şema `tools/gt_check.py` ile doğrulanır (`--finalize` taslağı GT'ye çevirir).
Araçlar: `tools/render_gt_ref.py` (id'li referans PNG / `--raw` ham), `tools/gt_draft.py` (tahminden taslak; holdout için boş
şablon), `annotate.py <dxf> --view x0,y0,x1,y1 --serve 8766 --open` (kırpılmış görünüm, Kaydet doğrudan taslağa yazar).

## Şema (özet)
- `source`, `units_per_meter`, `floor{rooms, doors, windows}`, `meta{status, tier, holdout, source, method, note, ...}`.
- `rooms[]`: `id`, `name` (çizimdeki etiket, ham), `type` (ROOM_TYPES'tan; boş olabilir), `kind` ∈ {daire içi, ortak, teknik, dış}
  (zorunlu; hangi tabloya bağlanacağını belirler), `polygon` (kapalı olmayan nokta listesi, bitiş noktası tekrarlanmaz).
- `doors[]`: `id`, `hinge` (menteşe; sürgülüde açıklık orta noktası), `width`, `connects` [oda id, oda id],
  `subtype` ∈ {sliding, elevator} (isteğe bağlı).
- `windows[]`: `a`, `b` (cam çizgisi uçları, en yakın oda kenarına hizalı).

## Kurallar
1. **Mahal = çizimde etiketi olan ya da mimari olarak ayrı her kapalı alan** (çekirdek: merdiven, asansör, aydınlık, şaft;
   dış: balkon, teras, veranda, sahanlık). Etiketsiz mahaller de GT'ye girer (`name` çizimde yoksa mimari ad, örn. MERDİVEN).
2. **Alan yazısı kanıt, geometri GT'dir**: poligon çizimdeki duvar iç yüzünü izler; yazı alanı ile ±%20 sapma normaldir.
3. **Küçük şaft kuralı (2026-09-15):** alanı ≤ `config/eval.yaml shaft_max_m2` (1 m²) olan şaft/teknik mahaller
   (`kind: teknik` ya da adı ŞAFT/SHAFT) GT'ye yazılır ama **oda F1'e girmez**; evaluate ayrı `shaft` satırında sayar
   (tp / fn). Neden: algılama alt sınırı `graph.min_room_area_m2` 1 m²; bu mahaller elektrik tasarımında oda değil, geçiş
   noktasıdır.
4. **Sürgülü kapı** `doors` içinde `subtype: sliding`, konum açıklığın orta noktası; asansör kapısı `subtype: elevator`.
5. **Holdout dosyaları (config/holdout.yaml) kör etiketlenir**: tahmin gösterilmez, yalnız ham çizim + boş şablon
   (`meta.method: blind`); geliştirme dosyaları `assisted` (tahminden taslak, insan düzeltir).
6. **Kaynak profili cevapları GT'den türetilebilir** (`hitl/cli.py --answered-by gt`): birim, alan uyuşmazlığı, kapı tarafı,
   etiketsiz bölge tipi; katman sınıfı sorularına GT cevap veremez (insan, `answered_by: human`).
7. Gerçek proje adları GT dosyasında yer almaz (src02: `src02-NN` kimliği; eşleme `data/dataset/src02/MAPPING.md`, repoda yok).
