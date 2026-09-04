# HITL soru adayları

Tek dosyada görülen, kural yazılmayan durumlar. Her madde ileride Validator issue tipi /
HITL sorusu olmaya adaydır. Biçim: **durum** · dosya · pipeline ne yaptı · sorulması gereken
soru ve seçenekler. Bir desen ≥3 dosyada tekrar ederse sinyal olur (CLAUDE.md §7).

| # | Durum | Dosya | Pipeline | Soru adayı | Seçenekler |
|---|---|---|---|---|---|
| 1 | Duvar çıkıntıları arasındaki küçük cep etiketin "dışlayıcı" bölgesi seçildi; asıl mekân Hol ile birleşik | tip-4 (ANTRE) | 3.1 m² cep = ANTRE, HOL ayrı | "ANTRE ile HOL aynı mekân mı?" | tek oda (takma ad) / iki oda / kapı var |
| 2 | Kapısız ~1 m açıklıkla ayrılan iki etiket | tip-4 (ANTRE/HOL) | büyük mühürde ayrıldı → 2 oda | "Bu açıklık kapı mı, geçiş mi?" | kapı / geçiş (aynı oda) / duvar |
| 3 | 'yazi-KAPIPENCERE' / 'KAPIPENCEREYAZISI' katmanındaki yazı çizgileri Hol ve Balkon'u kesiyor | KAYAPINAR | çizgiler duvar sanıldı, Hol 4.4/6.7 m² | "Bu katman ne?" | duvar / yazı-açıklama / mobilya / yoksay |
| 4 | Tezgâh modül çizgileri (33 cm, paralel) mutfağı bölüyor — mimar hatası olabilir | KAYAPINAR (Mutfak) | duvar çifti sanıldı, 7.0/10.7 m² | "Mutfağın ortasındaki çizgi duvar mı?" | duvar / tezgâh (yoksay) |
| 5 | Duş kabini camı 4 cm çift çizgi, boydan boya | tip-1 (BANYO) | duvar sanıldı (6 cm eşiğiyle çözüldü — ≥3 dosyada görülürse sinyal) | "Bu ince bölme duvar mı?" | duvar / cam bölme / mobilya |
| 6 | Merdiven basamakları 'kapi' katmanında | input-2-clean | bariyer oldu, merdiven alanı bölündü (ladder filtresiyle çözüldü) | "Bu katmandaki çizgiler ne?" | kapı / merdiven / duvar |
| 7 | Sürgülü balkon kapısı kapı katmanında düz çizgi, yay yok | input-2-clean (Balkon) | tek bariyer bu çizgiydi; kaldırılınca 87 m² sızıntı | "Bu açıklık?" | sürgülü kapı / pencere / geçiş |
| 8 | Aynı alanda iki bölge etiketi (VESTİYER+ODA, KİLER+SOFA, GİRİŞ+VESTİYER) | tip-11, tip-14, tip-15 | takma ad birleştirme uygulandı (GT yok) | "Tek mekân mı?" | tek oda + takma ad / iki oda |
| 9 | Kapı geometrisi hiç çizilmemiş, sadece duvar boşluğu | 1148 | başka yaylardan sahte kapılar | "Bu boşluk kapı mı?" (her boşluk) | kapı / geçiş / pencere / hiçbiri |
| 10 | Çizimde olmayan (unutulmuş) kapılar; SALON'a kapı yeri bile yok | tip-1 (d2/d3/d4) | bulunamadı (doğru) | "Eksik kapı ekleyelim mi?" | ekle (nereye) / yok |
| 11 | Revit oda etiketi kutusu (zone stamp) 'Structural - Bearing' katmanında kapalı polyline | 536_2 | duvar çifti sanılıp oda kutuya hapsoldu (etiket-çerçevesi filtresiyle çözüldü) | "Bu küçük kapalı çerçeve ne?" | etiket kutusu / kolon / şaft / duvar |
| 12 | Tesisat şaftı (60x60, içinde daire) oda köşesinde | tip-2 | odaya dahil edildi | "Bu kutu?" | şaft (dışla) / kolon (dışla) / oda içi |
| 13 | İkiz/aynalı daire tek çizimde; bir daire etiketsiz | bungalov-mumbai, HouseProject11 | atlandı | "Kaç daire var?" | 1 / 2 / n |
| 14 | Bina dışındaki not ('FRANSIZ BALKON KORKULUK', 'betonarme subasman merdiveni') oda sözlüğüne takılıyor | KAYAPINAR, 110-118, 183 | arka planı oda yaptı (kenar kuralıyla çözüldü) | "Bu yazı bir oda etiketi mi?" | evet / hayır (not) |
| 15 | Mahal listesi tablosu (döndürülmüş) plan sanıldı | tip-8, 536_2 | kapı-yayı kanıtı ile çözüldü | "Bu görünüm ne?" | kat planı / tablo / lejant |
| 16 | 'ODA SİCİL NO :' gibi kapak yazıları 'oda' etiketi sanıldı | 536_2, 1481 | etiket kuralı sıkılaştırıldı | "Bu metin oda adı mı?" | evet / hayır |
| 17 | Bakanlık dosyalarında oda adı INSERT ATTRIB'inde (MAHAL), TEXT değil | tip-1..9 | ATTRIB okuma eklendi | "Oda adları nerede?" | metin / blok özniteliği / yok |
| 18 | Kapı kanadı yayı 'kapi' katmanı olmayan anonim blok içinde; insert noktası geometriden uzak | hafif çelik, 536_2 | blok yayı + menteşe bbox kuralı ile çözüldü | "Bu blok kapı mı?" | kapı / pencere / mobilya |
| 19 | Pencere bloğunda 630 m uzakta aykırı parça | tip-6 ('90LIK PENCERE') | bbox patladı (5 m medyan filtresiyle çözüldü) | — (teknik) | — |
| 20 | Hafif çelik kaplama çift çizgileri (1-2 cm) sahte pencere üretiyor | hafif çelik 70 | 11 sahte pencere (bekletildi, yapım sistemine özgü) | "Bu paralel çizgiler pencere mi?" | pencere / kaplama / yoksay |
