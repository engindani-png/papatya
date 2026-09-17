# Handoff: Evolog U14 · arayüz yenilemesi

## Özet
Mevcut Evolog PWA'sının 8 ekranı yeniden tasarlandı. Renk ve ses korundu (koyu yeşil zemin, amber vurgu, sıkışık büyük harf etiketler); değişen şey **yapı ve hiyerarşi**: her kart hairline çerçeveli teknik bir nesne, köşe yuvarlaması sıfır, tüm ekran 16px tek kenar ızgarasına oturuyor, tipografi ölçeği 8 adıma indirildi.

Tasarımın çözdüğü asıl problem: **tarihi kesinleşmiş maç ile TBF'nin henüz tarih ilan etmediği maç görsel olarak ayrıştı.** 22 maçın 20'si belirsiz; veli yanlış güne gitmesin diye iki kart tipi hiçbir stil paylaşmıyor.

## Bu paketteki dosyalar hakkında
`Evolog Ekranlar.dc.html` ve `Evolog Spec.dc.html` **tasarım referansıdır** — HTML ile çizilmiş maket, doğrudan kopyalanacak üretim kodu değil. Görev bu maketleri **mevcut uygulamanın kendi ortamında** (mevcut PWA'nın HTML/CSS/JS yapısı, bileşenleri, veri katmanı) yeniden üretmektir. Veri akışı, TBF çekme mantığı, `data/` klasörü, yönlendirme — hiçbiri değişmiyor. Değişen yalnızca sunum katmanı.

En hızlı yol genelde şudur: mevcut `:root` değişkenlerini `tokens.css` ile değiştirmek, sonra ekran ekran markup'ı sadeleştirmek.

## Fidelity
**Yüksek (hi-fi).** Renkler, tipografi, boşluklar ve durumlar nihai değerlerdedir; `tokens.css` içindeki değerler birebir kullanılmalı. Etkileşim akışları maketlerde statik gösterildi — davranış mevcut uygulamada zaten var.

## Ekranlar

### 01 · Maçlar (veli, ana ekran)
- **Amaç:** veli tek bakışta "bir sonraki maç ne zaman, nerede" cevabını alır.
- **Düzen:** başlık (58px) → 2'li segment (Takımımız / Lig Geneli, 40px) → içerik (16px kenar) → alt sekme çubuğu (56px).
- **Sıradaki maç kartı:** amber çerçeve (`--amber-line`), sol 3px amber şerit. İki takım adı Barlow Condensed 19px, aralarında "VS". Altında tarih/saat satırı (13px `--paper-2`), salon (`--muted`). Maç değiştiyse `--amber-wash` zeminli, sol 3px amber şeritli not: "DEĞİŞTİ · önce 3 Eki Cum 18:30 idi". En altta 4 hücreli geri sayım ızgarası (gün/saat/dakika/saniye), her hücre hairline çerçeveli, sayı Condensed 22px.
- **Son maç:** tek satır kart — sol tarih bloğu, ortada iki takım + skor, sağda "GALİBİYET" rozeti (`--win` dolgu, `--ink` metin). Çeyrek skorları 10px tek satır: 18-8 · 16-12 · 19-9 · 14-9.
- **Yaklaşan maçlar başlığı:** sağında iki sayaç — "2 KESİN" (amber) ve "20 BEKLİYOR" (`--muted-deep`).
- **Liste:** kesin maçlar `.event`, belirsizler `.event--tbd` (aşağıdaki kural).
- **Alt sekme:** 5 hücre, aktif olanın üstünde 2px amber çizgi + amber etiket.

### 02 · Puan durumu
- 12 takım, **yatay kaydırma yok** — sütunlar # / TAKIM / O / G / M / AV / P olarak 390px'e sığdırıldı (`grid-template-columns: 24px 1fr 26px 26px 26px 34px 30px`).
- Başlık satırı 9px `.unit`, altında 1px `--line` kuralı; satırlar arası `--line-soft`.
- Takım logosu yok (mevcut uygulamadaki kırık görsel kutuları kaldırıldı).
- Altta açıklama: kısaltmalar + "Fikstür, skor ve puan durumu TBF sayfalarından otomatik çekilir."

### 03 · Kadro
- İki bölüm: **Maç kadrosu** (forma numarası olan 11–12 oyuncu) ve **Lisanslı · maç oynamadı** (kalanlar).
- Satır: `38px | 1fr | auto` → forma no (Condensed 23px amber) / ad (14px) / sayı ort. (Condensed 18px).
- Numarasızlarda amber "—", sağda doğum yılı (`--muted-deep`).

### 04 · Oyuncu profili
- Kadro listesinin üstüne açılan yarım sayfa (üstten 250px), `--ink-raised` zemin, üst kenarında amber hairline.
- Başlık: forma no Condensed 34px amber + ad Condensed 22px + "2014 doğumlu · 5 maç · ilk beş".
- 6 hücreli istatistik ızgarası (3 sütun): büyük sayı Condensed 26px, altında `.unit` etiket ve toplam.
- Altta "Maç maç" tablosu: MAÇ / DK / SAY / RİB.

### 05 · Antrenman (veli)
- Üstte 7 günlük hafta şeridi; antrenman olan günler amber dolgu + `--ink` metin, diğerleri boş hairline hücre.
- **Bu hafta:** her antrenman `.event` (sol amber şerit) — gün+tarih solda Condensed 20px, saat sağda amber Condensed 20px, altında salon ve tür.
- **Gelecek hafta:** program girilmemişse `.event--tbd` — kesikli çerçeve, taralı zemin, "21 – 27 Eylül programı henüz açıklanmadı."
- **Salonlar:** düz metin listesi (ad · semt).
- Mevcut uygulamadaki tamamen boş "Antrenman programı girilmemiş." ekranı yerine, boş hâl de bu kesikli kutu olarak gösterilir.

### 06 · Ayarlar
- Takım sekmesinden açılan yarım sayfa (üstten 300px), arkası %75 karartılır.
- **Bildirimler:** tek satır + kare anahtar (44×24, kapalıyken 16×16 `#4d6b61` topuz). Altında ne zaman bildirim geldiğini anlatan 11.5px metin.
- **Uygulama:** Takım / Veri güncelliği / Antrenör paneli satırları; sonuncusunun sağında amber "ŞİFRELİ ›".

### 07 · Yoklama (antrenör)
- Başlık "ANTRENÖR PANELİ" + 3'lü sekme (Yoklama / Program / Oyuncular) — aktif olan amber dolgu.
- Antrenman seçimi: 2 kart yan yana (seçili olan amber çerçeve + `--amber-wash`), altında tarih/saat satırı ve "BAŞKA GÜN".
- Toplu işlemler: "HEPSİ GELDİ" / "TEMİZLE" hairline butonlar; sağda "7/22 işaretli" sayacı.
- **Oyuncu satırı:** solda forma no, sağda ad + 4 butonlu ızgara (GELDİ / GEÇ / YOK / İZİNLİ), her buton min 44px yükseklik hedefi. Seçili olan dolu: geldi `--win`, geç `--amber`, yok `--loss`, izinli `--muted` — metin `--ink`. Seçili olmayan: hairline çerçeve, `--muted` metin.
- Altta sabit çubuk: solda durum metni, sağda amber KAYDET.

### 08 · Oyuncu analizi (antrenör)
- "← KADROYA DÖN" satırı, ardından oyuncu başlığı ve 3 hücreli özet.
- **Gelişim kartları:** her metrik için başlık + trend rozeti (↗ YÜKSELİYOR `--win` / → SABİT `--muted`) + sağda "ort X"; içinde 62px yüksekliğinde çizgi grafik — amber 1.6px çizgi, 2.6r noktalar, ortalama kesikli `rgba(232,240,236,.22)` çizgi. Eksen etiketi yalnız iki uçta (2 EYL / 14 EYL).
- Altta maç maç tablosu.

## Kesin / belirsiz kuralı (en önemli kısım)
| | Kesin | Belirsiz |
|---|---|---|
| Çerçeve | 1px düz `--line` | 1px **kesikli** `--line-dash` |
| Zemin | yok | 135° tarama `--hatch` |
| Sol şerit | 3px `--amber` | yok |
| Amber kullanımı | serbest | **hiçbir yerinde yok** |
| Tarih bloğu | gün sayısı + "EYL ÇAR" | "?" + "3. HAFTA" |
| Saat | her zaman yazılı | **satır hiç basılmaz** |
| Alt metin | salon adı | "Tarih TBF'de ilan edilmedi" |
| Geri sayım | yalnız burada | yok |

Değişen maç **kesin kalır**; üstüne amber "DEĞİŞTİ" şeridi ve eski tarih eklenir. İki tip asla aynı görünmemeli: veli listeyi kaydırırken belirsizler tek gri blok olarak okunur, kesin maç amber çizgisiyle tek başına ayrışır. `tokens.css` içindeki `.event` / `.event--tbd` sınıfları bu kuralı kodla birlikte taşır.

## Etkileşim ve durumlar
- Sekme değişimi anında, geçiş animasyonu yok (PWA hissi için 0ms tercih edildi).
- Yarım sayfalar (oyuncu profili, ayarlar) alttan yukarı 200ms `cubic-bezier(.2,.8,.2,1)` ile açılır; arka plan `rgba(6,12,10,.75)`.
- Yoklama butonu dokunuşta anında dolar; kaydedilmemiş değişiklik varsa alt çubuk metni "7 işaretli · 15 bekliyor" olarak kalır, kaydedilince "Kaydedildi · 18.09 19:34".
- Geri sayım saniyede bir güncellenir; maç başlayınca kart "OYNANIYOR" durumuna geçer (amber şerit kalır, geri sayım yerine "başladı" metni).
- Odak halkası: `2px solid var(--amber)`, offset 2px. Tarayıcı varsayılan mavi halka bırakılmaz.
- Boş hâller her zaman kesikli kutu + tek cümle açıklama; boş ekran bırakılmaz.

## Durum (state)
Yeni state gerekmiyor. Tasarımın ihtiyaç duyduğu alanlar mevcut veriden türetilebilir:
- `match.dateConfirmed: boolean` — TBF tarih ilan etti mi (kart tipini bu seçer)
- `match.previousDate` — doluysa "DEĞİŞTİ" şeridi basılır
- `match.week` — belirsiz kartta tarih yerine yazılır
- `training.weekPublished: boolean` — gelecek hafta kutusunun tipi
- `attendance[playerId]: 'geldi' | 'gec' | 'yok' | 'izinli' | null`

## Tasarım değerleri
Tamamı `tokens.css` dosyasında; okunabilir tablo hâli `Evolog Spec.dc.html` içinde.

## Varlıklar
Görsel varlık yok. Sponsor logosu, stok fotoğraf, çocuk fotoğrafı ve uydurma istatistik **bilinçli olarak yok**. Takım logoları maketlerden çıkarıldı (mevcut uygulamada kırık görsel kutusu olarak görünüyorlardı); gerçek logo dosyaları varsa 34px kare, çerçevesiz basılabilir. İkon gerekirse Lucide, stroke-width 1.5.

Tüm veriler gerçek: 23 Eylül Eyüpsultan maçı, 67-38 Galatasaray (B) galibiyeti, 22 kişilik kadro forma numaralarıyla, Cuma TEV 19:30 / Pazar Maltepe TOKİ 11:00 antrenmanları.

## Dosyalar
- `Evolog Ekranlar.dc.html` — 8 ekranın 390×844 artboard'ları (tarayıcıda doğrudan açılır)
- `Evolog Spec.dc.html` — renk / tipografi / boşluk tablosu
- `tokens.css` — kopyala-yapıştır değişkenler + iki kart tipinin sınıfları
- `claude-code-prompt.md` — Claude Code CLI'ye verilecek hazır komut
- `mevcut-uygulama/` — yenileme öncesi 10 ekran görüntüsü (karşılaştırma için)
