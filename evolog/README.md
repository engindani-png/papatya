# Evolog Kız Basketbol — Takım Uygulaması

Mobil uyumlu (telefona kurulabilen) takım uygulaması: kadro, yaklaşan maçlar,
lig puan durumu ve antrenman programı. Maç sonuçları ve puan durumu **TBF
sayfalarından otomatik çekilir**.

## Yaş grupları

Uygulama şu an yalnızca **U14 Kız Siyah** takımını taşır (U16/U18 kaldırıldı;
`scripts/tbf_config.json` + `evolog/app.js` içindeki `AGES` listesine satır
eklenerek geri getirilebilir). Alt çubuğun sağ ucundaki
takım sekmesinden geçiş yapılır; seçim tarayıcıda saklanır, yani uygulama bir
sonraki değişikliğe kadar hep o takımla açılır. Aynı sayfada maç bildirimleri
yaş yaş açılıp kapatılır (bir veli birden fazla takıma abone olabilir).

Her takımın verisi kendi klasöründe: `data/u14/`.
Yeni bir yaş grubu açıldığında `scripts/tbf_config.json` içindeki `teams`
listesine bir satır eklemek ve `evolog/app.js` içindeki `AGES` listesine aynı
anahtarı yazmak yeterli.

## Yayına alma

1. GitHub → **Settings → Pages** → Source: `Deploy from a branch`, Branch: `master` / `root`.
2. Uygulama adresi: `https://<kullanıcı-adı>.github.io/papatya/evolog/`
3. Telefonda o adresi açıp tarayıcı menüsünden **“Ana ekrana ekle”** deyin —
   uygulama tam ekran, kendi ikonuyla açılır ve çevrimdışı da çalışır.

Arayüzü örnek verilerle görmek için adresin sonuna `?demo=1` ekleyin.

Tek dosyalık, kendi kendine yeten bir önizleme (`evolog/preview.html`) da var;
veriyi sayfaya gömer, sunucu gerektirmez:

```bash
python3 scripts/build_artifact.py        # evolog/preview.html üretir
```

## Tasarım

Loş salonlarda okunacağı için bilinçli olarak tek temalı: zemin derin saha
yeşili (`#0f1e1c`), aksan parke/top kehribarı (`#f2a03d`), galibiyet ve
mağlubiyet için aksandan ayrı anlamsal renkler. Skorbord rakamları ve
etiketler sıkışık **Oswald**, gövde metni **Karla**. Maçlar, kadro ve
antrenman aynı üç sütunlu çizelge ritmini paylaşır (sol oluk · içerik · etiket);
kart görünümü yalnızca skorbord için ayrılmıştır, takımın kendi satırları
kehribar rayla ayrışır.

## Verileri düzenleme

Tüm veriler `data/` klasöründeki JSON dosyalarında. GitHub üzerinden doğrudan
düzenleyip kaydedebilirsiniz; uygulama bir sonraki açılışta günceli gösterir.

| Dosya | İçerik | Nasıl güncellenir |
|---|---|---|
| `data/<yaş>/team.json` | Kadro, teknik kadro | Kadro otomatik, teknik kadro elle |
| `data/<yaş>/training.json` | Antrenman gün/saat/salon | Yönetim ekranından |
| `data/<yaş>/league.json` | Fikstür, skorlar, puan durumu | **Otomatik** (TBF senkronizasyonu) |

Sunucuda antrenman programı git ağacının dışında tutulur
(`/var/lib/evolog/training-<yaş>.json`); nginx onu `data/<yaş>/training.json`
adresinde sunar. Yönetim ekranı istekleri `?age=<yaş>` ile gönderir.

### Kadro (`data/<yaş>/team.json`)

```json
{ "no": 7, "name": "Ayşe Yılmaz", "position": "Guard", "birthYear": 2012, "height": 168 }
```

`height` bilinmiyorsa `null` bırakın; uygulama boş alanları gizler.

### Antrenman (sunucuda `/var/lib/evolog/training-<yaş>.json`)

> ⚠️ Antrenman programı **depoda durmaz**. nginx `/data/<yaş>/training.json`
> adresini doğrudan `/var/lib/evolog/training-<yaş>.json` dosyasına bağlar;
> depoya konan bir kopya hiçbir zaman yayına girmez (senkronizasyon zaten
> `git reset --hard` yapıyor, düzenlemeyi silerdi). Programı **yönetim
> ekranından** girin: `/yonetim.html`.

`day`: 1 = Pazartesi … 7 = Pazar. Salonu `venues` listesine ekleyip
seansta `venue` alanına salonun `id` değerini yazın. `maps` alanına konulan
bağlantı uygulamada **“Yol tarifi”** düğmesi olarak çıkar.

Tatil/iptal günlerini `exceptions` listesine ekleyin.

**`weekStart`** — programın ait olduğu haftanın pazartesisi (`2026-09-14`).
Yönetim ekranındaki “Program hangi hafta için?” şeridi bunu yazar. Hafta
geçtiğinde uygulama seansları kesin bilgi gibi göstermez; “önümüzdeki haftanın
programı henüz açıklanmadı” der ve eski programı *Geçen haftanın programı*
başlığı altına alır. Aynı ilke maç tarihlerinde de geçerli: kesinleşmemiş
bilgi veliye kesinmiş gibi gösterilmez.

Program değiştiğinde (`server/evolog_push.py`) velilere tek bir bildirim
gider: yalnızca **değişen günler** yazılır — “Cumartesi antrenman yok ·
Pazar 11:00 Basketbol ve Kuvvet (Maltepe Toki)”. En son bildirilen program
`/var/lib/evolog/training-seen-<yaş>.json` içinde tutulur.

## TBF senkronizasyonu (önemli kısım)

`scripts/tbf_sync.py` TBF API'sini okuyup her takım için
`data/<yaş>/league.json` dosyasını üretir. Takımlar sırayla çekilir; birinin
çekimi başarısız olursa **diğerleri etkilenmez** ve o takımın önceki verisi
korunur. Tek takım denemek için `--team u14`. `.github/workflows/tbf-sync.yml` bunu günde 4 kez
(TR saatiyle ~06:00, 12:00, 18:00, 22:00) çalıştırır ve değişiklik varsa
otomatik commit'ler.

### Kurulum

`scripts/tbf_config.json` içinde lig kimliği tanımlı:

```json
"seasonId": "174",
"teams": [
  { "key": "u14", "leagueId": "22859", "teamProcessId": "269325", … },
  { "key": "u16", "leagueId": "22861", "teamProcessId": "270342", … },
  { "key": "u18", "leagueId": "22863", "teamProcessId": "269435", … }
]
```

Lig kimlikleri TBF'de **il bazında 16'şarlı bloklar** halinde diziliyor
(Büyük E/K · U10 · U11 · U12 · U14 · U16 · U18 · Ümit, her yaşta önce erkek
sonra kız). İstanbul 2026-2027 bloğu **22850–22865**. Sezon değişince bu
numaralar da değişir.

Numaralar TBF adreslerinden gelir:

- `www.tbf.org.tr/ligler/**22859**/mac-detay/346856` → lig
- `www.tbf.org.tr/ligler/22859/takim-detay/**269325**/maclar` → takım

Sezon veya lig değişirse yalnızca bu iki alanı güncelleyin. Fikstür için
önce takımın kendi maç sayfası denenir (yalnızca Evolog'un maçları, en
güvenilir kaynak), tutmazsa lig geneli fikstür adresleri denenir.

Script, puan durumu ve fikstür için birkaç aday adresi (`candidatePaths`)
sırayla dener ve **ilk ayrıştırabildiğini** kullanır; hangisinin tuttuğunu
`data/league.json` içindeki `source` alanına yazar. Doğru adresi biliyorsanız
doğrudan `sources[].url` alanına yazın, deneme atlanır.

`teamAliases` içinde takımın TBF'de yazıldığı adı bulundurun
(örn. `"evolog spor kulübü"`); uygulama takımınızı bununla eşleştirip
puan durumunda vurgular ve maçlarını işaretler.

**Actions → “TBF veri senkronizasyonu” → Run workflow** ile elle
çalıştırabilirsiniz. Çalışan adres bulunamazsa iş akışı kaydında denenen
tüm adresler ve nedenleri tek tek listelenir.

### ÖNEMLİ: TBF bulut sunucularını engelliyor

Ölçüm sonucu: `tbf.org.tr` GitHub Actions'tan gelen isteklere **anında 403
Forbidden** dönüyor — hem düz HTTP isteğine, hem de gerçek bir Chromium
tarayıcıyla (Türkçe dil/saat dilimi, normal tarayıcı kimliği) açıldığında.
Yanıt 150 ms içinde geliyor, bir doğrulama sayfası ya da JS sınavı yok;
yani engel isteğin *neye benzediğiyle* değil, **nereden geldiğiyle** ilgili:
veri merkezi IP'leri (Azure/AWS) baştan reddediliyor. Aynı adresler sizin
telefonunuzda ve bilgisayarınızda sorunsuz açılıyor.

Bu yüzden zamanlanmış iş akışı tek başına veri çekemez. Çalışan üç yol var:

**1. Kendi bilgisayarınızdan çekin (en pratik).** Depoyu bir kez indirin,
maç sonrası tek komut:

```bash
./scripts/yerel_guncelle.sh          # Windows: scripts\yerel_guncelle.cmd
```

Veriyi sizin bağlantınızdan çeker, `data/league.json` dosyasını günceller,
commit'leyip push'lar. Uygulama birkaç dakika içinde güncel veriyi gösterir.
Ek kurulum gerekmez (yalnızca Python 3 ve git).

**2. Kendi bilgisayarınızı runner yapın (kur-unut).** GitHub'da
*Settings → Actions → Runners → New self-hosted runner* ile evdeki bir
bilgisayarı ekleyip iş akışındaki `runs-on: ubuntu-latest` satırını
`runs-on: self-hosted` yapın. Zamanlanmış çekim sizin bağlantınızdan
çalışır, hiçbir şeye dokunmanız gerekmez.

**3. Sayfayı kaydedip besleyin (internet gerekmez).** TBF sayfasını
tarayıcıda açıp Ctrl+S ile kaydedin, sonra:

```bash
python3 scripts/tbf_sync.py --from-file puan-durumu.html --kind standings
python3 scripts/tbf_sync.py --from-file maclar.html      --kind fixtures
```

Her komut yalnızca kendi bölümünü günceller, diğerini olduğu gibi korur.

Engelin kalkıp kalkmadığını görmek için:

```bash
python3 scripts/tbf_sync.py --probe
```

Her aday adresi dener; HTTP durumunu, sayfa boyutunu, `<title>` değerini ve
bulunan tabloların başlıklarını yazar.

### Neyi nasıl okur

- **Puan durumu:** başlığında “Takım” ve “Puan/P” geçen tabloyu bulur;
  O / G / M / A / Y / AV / P sütunlarını başlık adlarından eşler.
- **Fikstür:** tarih içeren satırları maç sayar. `17.01.2026`, `2026-01-17`,
  `17/01/2026` biçimlerini; `61 - 48` skorlarını; ayrı sütundaki ya da
  tarihle aynı hücredeki saati; salon adını tanır.
- **Maç istatistikleri:** Fikstür tablosundaki `/mac-detay/<id>` bağlantılarından
  maç kimlikleri toplanır; oynanmış maçlar için detay sayfası açılıp **çeyrek
  skorları** ve **iki takımın oyuncu istatistikleri** (DK/SAY/RİB/AST/TOP Ç/BLK/
  HATA/FAUL) okunur. "TOPLAM" satırı atlanır. Uygulamada maça dokununca açılır.
  Bir kez çekilen detay sonraki senkronizasyonlarda korunur, aynı sayfa tekrar
  indirilmez. `matchDetail.onlyOurMatches` ile yalnızca Evolog maçları,
  `maxMatches` ile üst sınır ayarlanır.
- Çekim başarısız olursa **önceki veri korunur**, uygulamanın üstünde uyarı
  görünür — ekran hiçbir zaman boşalmaz.

### JSON API kaynağı

TBF tarafı HTML yerine JSON dönüyorsa `type: "json"` kullanın ve alan
eşlemesini yazın (örneği `tbf_config.json` içindeki `jsonMappingExample`):

```json
{ "kind": "fixtures", "type": "json", "url": "...", "rowsPath": "data.matches",
  "fields": { "date": "matchDate", "home": "homeTeam.name", "homeScore": "homeTeam.score" } }
```

### Yerelde deneme

```bash
# Kaydedilmiş bir sayfayı ayrıştır (adrese gerek yok)
python3 scripts/tbf_sync.py --from-file puan.html --kind standings --dry-run

# Yapılandırmadaki kaynaklardan çek, dosyaya yazmadan göster
python3 scripts/tbf_sync.py --dry-run

# Uygulamayı yerelde aç
python3 -m http.server 8000   # -> http://localhost:8000/evolog/
```

Script yalnızca Python standart kütüphanesini kullanır; kurulum gerekmez.
