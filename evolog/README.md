# Evolog U14 Kız — Takım Uygulaması

Mobil uyumlu (telefona kurulabilen) takım uygulaması: kadro, yaklaşan maçlar,
lig puan durumu ve antrenman programı. Maç sonuçları ve puan durumu **TBF
sayfalarından otomatik çekilir**.

## Yayına alma

1. GitHub → **Settings → Pages** → Source: `Deploy from a branch`, Branch: `master` / `root`.
2. Uygulama adresi: `https://<kullanıcı-adı>.github.io/papatya/evolog/`
3. Telefonda o adresi açıp tarayıcı menüsünden **“Ana ekrana ekle”** deyin —
   uygulama tam ekran, kendi ikonuyla açılır ve çevrimdışı da çalışır.

Arayüzü örnek verilerle görmek için adresin sonuna `?demo=1` ekleyin.

## Verileri düzenleme

Tüm veriler `data/` klasöründeki JSON dosyalarında. GitHub üzerinden doğrudan
düzenleyip kaydedebilirsiniz; uygulama bir sonraki açılışta günceli gösterir.

| Dosya | İçerik | Nasıl güncellenir |
|---|---|---|
| `data/team.json` | Kadro, teknik kadro | Elle |
| `data/training.json` | Antrenman gün/saat/salon | Elle |
| `data/league.json` | Fikstür, skorlar, puan durumu | **Otomatik** (TBF senkronizasyonu) |

### Kadro (`data/team.json`)

```json
{ "no": 7, "name": "Ayşe Yılmaz", "position": "Guard", "birthYear": 2012, "height": 168 }
```

`height` bilinmiyorsa `null` bırakın; uygulama boş alanları gizler.

### Antrenman (`data/training.json`)

`day`: 1 = Pazartesi … 7 = Pazar. Salonu `venues` listesine ekleyip
seansta `venue` alanına salonun `id` değerini yazın. `maps` alanına konulan
bağlantı uygulamada **“Yol tarifi”** düğmesi olarak çıkar.

Tatil/iptal günlerini `exceptions` listesine ekleyin.

## TBF senkronizasyonu (önemli kısım)

`scripts/tbf_sync.py` TBF sayfalarındaki tabloları okuyup `data/league.json`
dosyasını üretir. `.github/workflows/tbf-sync.yml` bunu günde 4 kez
(TR saatiyle ~06:00, 12:00, 18:00, 22:00) çalıştırır ve değişiklik varsa
otomatik commit'ler.

### Kurulum — tek yapmanız gereken adres girmek

`scripts/tbf_config.json` dosyasındaki `sources` listesine, TBF'de İstanbul
U14 Kız **A Grubu**'nun puan durumu ve fikstür sayfalarının adreslerini yazın:

```json
"sources": [
  { "kind": "standings", "type": "html", "url": "https://.../puan-durumu-sayfasi", "enabled": true },
  { "kind": "fixtures",  "type": "html", "url": "https://.../fikstur-sayfasi",    "enabled": true }
]
```

Ayrıca `teamAliases` içinde takımın TBF'de yazıldığı adı bulundurun
(örn. `"evolog spor kulübü"`); uygulama takımınızı bu adla eşleştirip
puan durumunda vurgular ve maçlarını işaretler.

Adresleri girdikten sonra **Actions → “TBF veri senkronizasyonu” → Run workflow**
ile ilk çekimi elle başlatabilirsiniz.

### Neyi nasıl okur

- **Puan durumu:** başlığında “Takım” ve “Puan/P” geçen tabloyu bulur;
  O / G / M / A / Y / AV / P sütunlarını başlık adlarından eşler.
- **Fikstür:** tarih içeren satırları maç sayar. `17.01.2026`, `2026-01-17`,
  `17/01/2026` biçimlerini; `61 - 48` skorlarını; ayrı sütundaki ya da
  tarihle aynı hücredeki saati; salon adını tanır.
- **Maç istatistikleri:** `league.json` içindeki bir maça `quarters` ve
  `boxscore` alanları eklendiğinde uygulama maça dokununca çeyrek skorlarını
  ve oyuncu istatistik tablosunu (SAY/RIB/AST/TOP Ç/BLK/HATA/FAUL) gösterir.
  TBF sayfası bu ayrıntıyı veriyorsa `boxscore` kaynağını da `sources`
  listesine ekleyip aynı yapıya doldurabilirsiniz; alan yoksa bölüm gizlenir.
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
