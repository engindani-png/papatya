# Yaş grupları (U14 · U16 · U18) — tasarım

**Tarih:** 2026-09-15 · **Durum:** onaylandı

## Amaç

Uygulama bugüne kadar tek takıma (U14 Kız) göre kuruluydu. Kulübün TBF'de bu
sezon kayıtlı **üç kız takımının** (U14, U16, U18) tümü uygulamaya girecek;
kullanıcı alt çubuğun sağ ucundan takım değiştirecek ve seçim **bir sonraki
değişikliğe kadar** kalıcı olacak.

TBF taraması sonucu: kulübün bu sezon erkek takımı yok (İstanbul U14/U16/U18
Erkekler liglerinin tam kadro listeleri kontrol edildi). U10/U11/U12, Büyük ve
Ümit liglerinde henüz fikstür açılmamış. Bu yüzden kapsam üç kız takımı.

| Yaş | Lig | leagueId | teamProcessId | TBF'deki adı |
|---|---|---|---|---|
| U14 | İstanbul U14 Kızlar 2026-2027 | 22859 | 269325 | EVOLOG DAÇKA ŞERİFALİ |
| U16 | İstanbul U16 Kızlar 2026-2027 | 22861 | 270342 | DAÇKA ŞERİFALİ SK |
| U18 | İstanbul U18 Kızlar 2026-2027 | 22863 | 269435 | EVOLOG DAÇKA ŞERİFALİ |

## Veri düzeni

Tek `data/league.json` yerine yaş başına klasör:

```
data/u14/league.json  data/u14/team.json
data/u16/league.json  data/u16/team.json
data/u18/league.json  data/u18/team.json
```

- `scripts/tbf_config.json` tek lig alanı yerine **`teams` listesi** tutar:
  her kayıtta `key` (u14/u16/u18), `leagueId`, `teamProcessId`, uygulamada
  görünecek ad ve lig etiketi. `seasonId` ve `apiBaseUrl` ortak kalır.
- `scripts/tbf_sync.py` bu liste üzerinde döner; her takım için puan durumu,
  fikstür, lig geneli fikstür, kadro ve maç detaylarını ayrı dosyaya yazar.
  Bir takımın çekimi başarısız olursa **diğerleri etkilenmez** ve o takımın
  önceki verisi korunur (mevcut davranışın takım bazına inmiş hali).
- Logolar ortak `evolog/logos/` klasöründe kalır — üç ligde ortak rakipler var,
  aynı logo iki kez indirilmez.
- **Geriye dönük uyum:** nginx `/data/league.json` ve `/data/team.json`
  adreslerini `/data/u14/...` dosyalarına yönlendirir. Telefonlardaki kurulu
  eski sürüm, kendini güncelleyene kadar boş ekran görmez.

Çekim sıklığı **saat başı** (`evolog-sync.timer`). Üç takım ~3 kat istek demek;
maç detayı bir kez çekilip saklandığı için normal turda fark küçük kalır.

## Uygulama — seçili yaş

- Seçim `localStorage`'da `evolog.age` (varsayılan `u14`). PWA bir sonraki
  değişikliğe kadar o takımla açılır.
- `app.js` içindeki sabit `DATA` yolu, seçili yaşa göre `../data/<key>/` olur.
- Yaş değişince: veri yeniden yüklenir, başlık · logo · lig etiketi o takımın
  bilgisine döner, ekran yeniden çizilir, sekme (Maçlar/Puan/Kadro/Antrenman)
  korunur.
- `sw.js` önbelleği üç takımın dosyalarını ayrı tutar (veri için "önce ağ,
  olmazsa önbellek" kuralı aynen geçerli). Önbellek adı artırılır.

## Alt çubuk ve takım sayfası

Mevcut dört sekmeli çubuk korunur; **sağ ucuna beşinci sekme** eklenir, üzerinde
seçili yaş yazar. Dokununca alttan sayfa açılır:

| Bölüm | İçerik |
|---|---|
| Takım | U14 · U16 · U18 — seçili olan işaretli |
| Ayarlar | Maç bildirimi (yaş yaş aç/kapa) · son veri saati · antrenman programını düzenle |

Ana ekrandaki kalıcı bildirim şeridi (`pushSlot`) **kaldırılır**; yeri burası.
Tek istisna: iPhone'da uygulama ana ekrana eklenmemişse bildirim hiç
çalışmadığından o uyarı bir kez görünür ve kapatılabilir (kapatılınca bir daha
çıkmaz, tercih `localStorage`'da).

## Bildirimler

- Abonelik kaydına (`subs.json`) `ages` alanı eklenir; `/api/push/subscribe`
  gövdesi bu listeyi taşır. Alan yoksa `["u14"]` varsayılır — mevcut aboneler
  bozulmaz.
- `server/evolog_push.py` üç `league.json` dosyasını okur, olayları takım
  bazında üretir ve her aboneye **yalnızca seçtiği yaşların** maçlarını
  gönderir. Bildirim başlığında takım adı geçer ("U16 · Maç bitti").
- Gönderilmiş olay kaydı (`notified.json`) yaş anahtarıyla ayrışır.

## Antrenman programı

Her yaşın kendi programı: `/var/lib/evolog/training-<key>.json`.

- `server/evolog_api.py`: `GET/POST /api/training?age=<key>`. Geçersiz veya
  eksik `age` → `u14` (eski istemciler çalışmaya devam eder).
- nginx `/data/training.json` yerine `/data/<key>/training.json` uçlarını
  servis eder; dosyalar git ağacının dışında kalmayı sürdürür.

### Giriş ekranı — dokunmayla

`yonetim.html` önce takım seçtirir, sonra seansları dokunarak girdirir:

- **Gün:** yatay Pzt–Paz şeridi, dokun-seç
- **Saat:** iOS tekerleği benzeri saat + dakika sütunları, 15 dakika adım;
  klavye açılmaz
- **Salon:** kayıtlı salonlardan seçim, "+ Yeni salon" ile ekleme
- Seans satırı tek dokunuşla kopyalanır (aynı saat, başka gün), çöp kutusuyla
  silinir

WhatsApp mesajı yapıştırıp çözümleme yolu korunur ama ikincil kestirme olur.

## "Yeni veri geldi" uyarısı

Arka plan tazelemesinde ekranda hiçbir şey çıkmaz. Üstteki durum göstergesi
sessizce yeni saate döner, kısa bir amber vurgu verir. Kullanıcı kendi
yenilediğinde kısa bilgi yazısı çıkmayı sürdürür.

## Geniş ekran / iPad

Şu an `.wrap` her ekranda 560 piksele sabit — iPad'de ortada dar şerit kalıyor.

- ≥ 768 px: içerik 900 piksele açılır, tablolar yatay kaydırma olmadan sığar
- ≥ 1024 px: maç listesi ve puan durumu yan yana iki sütun
- Alt çubuk ortalanır ve parmak genişliğinde kalır (tam genişliğe yayılmaz)
- Yatay/dikey çevirme ve tam ekran (standalone) desteklenir

## Kapsam dışı (bilinçli)

Ağustos "Seri A Ön Eleme" ligi (22221) · erkek takımlar (TBF'de yok) · veli
üyelik sistemi (kendi tasarımı var) · geçen sezon arşivi · U12 ve altı
(fikstür açılınca `teams` listesine bir satır eklenerek girer).

## Doğrulama

1. `tbf_sync.py` çalıştırılıp üç takımın `league.json` + `team.json` dosyaları
   ve içlerindeki puan durumu / fikstür / kadro sayıları kontrol edilir
2. Bir takımın çekimi kasten bozulup diğer ikisinin etkilenmediği görülür
3. Uygulama üç yaşta da açılır; yaş seçimi kapatıp açınca korunur
4. Bildirim kuru çalıştırma (`--dry`) ile abonenin yalnızca seçtiği yaşların
   olaylarını aldığı görülür
5. Antrenman programı üç takım için ayrı kaydedilir ve ayrı görünür
6. 390 px (telefon), 834 px (iPad dikey), 1194 px (iPad yatay) genişliklerinde
   ekran kontrolü; yatay kaydırma çubuğu çıkmamalı
