# VDS devir notu — 17 Eylül 2026

Bu dosya, **bilgisayarındaki Claude CLI oturumunun** işi devralması için yazıldı.
Bulut oturumunun ağı VDS'e ve `tbf.org.tr`'ye kapalı; senin ağın açık.

Kullanıcı Türkçe konuşuyor.

## Sistem

| | |
|---|---|
| Repo | `github.com/engindani-png/papatya`, dal `master` |
| Canlı site | https://evolog.213-159-6-115.sslip.io/evolog/ |
| VDS | `213.159.6.115` · uygulama `/var/www/evolog` · durum `/var/lib/evolog` |
| Kullanıcılar | Veliler. PWA olarak telefonlarına kurulu. |

Veri akışı: TBF → `scripts/tbf_sync.py` → `data/<yaş>/league.json` → git →
VDS'te cron `git pull` → nginx. Bildirimler `server/evolog_push.py`.

## Bugün yapılanlar (push'landı, son commit `5fb0185`)

1. **Maç düzeltmesi.** Eyüpsultan Belediyesi – Evolog (U14, 2. hafta)
   **23 Eylül Çarşamba 20:00**'ye alındı (önceki: 3 Ekim Cumartesi 18:30).
   `data/u14/overrides.json` içinde; senkronizasyon ezmez.

2. **Sahte tarih tespiti.** TBF fikstür servisi ilan edilmemiş maçlar için
   gerçek tarih yerine dolgu döndürüyor: her üç yaş grubunda da maçlar tam
   **9 gün arayla ve hep aynı saatte** diziliyor (U14'te 22 maçın 21'i 18:30).
   Her takımda **20/22 maç** bu durumda. `scripts/local_edits.py` bunları
   bulup `dateConfirmed=false` işaretliyor; uygulama o maçlarda gün/saat
   yerine "TBF'de kesinleşmedi" gösteriyor ve **geri sayımı yalnızca tarihi
   kesin maça** yapıyor.

3. **Değişiklik bildirimi.** `server/evolog_push.py` artık gün/saat
   değişikliğinde bildirim üretiyor. `--status` teşhis modu eklendi.

## Yapılacak

### A. Bildirimleri ayağa kaldır (acil)

**Bulgu:** VDS'teki cron şimdiye kadar yalnızca `git pull` yapıyordu;
`server/evolog_push.py` **hiç çalıştırılmamış**. Bu yüzden bugüne kadar
hiçbir push gitmemiş (maç sonuçları dahil).

```bash
cd /var/www/evolog && git pull && bash deploy/bildirim_kur.sh
```

Script pywebpush'u bulur/kurar, 5 dakikalık cron'u yazar, bekleyenleri
gönderir. `notified.json` sayesinde aynı bildirim ikinci kez gitmez.

Çıktıdaki `--status` satırlarını kullanıcıya raporla: abone sayısı,
bekleyen/gönderilmiş olaylar, pywebpush ve VAPID durumu.

### B. Canlıyı doğrula

```bash
curl -s https://evolog.213-159-6-115.sslip.io/data/u14/league.json \
  | python3 -c "import sys,json;f=[x for x in json.load(sys.stdin)['fixtures'] if str(x.get('matchId'))=='346858'];print(f[0]['date'],f[0]['time'],f[0].get('dateConfirmed'))"
# beklenen: 2026-09-23 20:00 True

curl -s https://evolog.213-159-6-115.sslip.io/evolog/sw.js | head -2
# beklenen: CACHE = "evolog-v16"
```

Site eski veriyi veriyorsa VDS'te `git pull` cron'u çalışmıyor demektir
(`/etc/cron.d/evolog`).

### C. Duyurunun kaynağı (kullanıcının asıl sorusu)

Maç saatinin değiştiği duyurusu TBF'de nerede yayınlandı? Senin ağın
`tbf.org.tr`'ye erişebiliyor.

- Lig `22859`, takım `269325`, maç `346858`
- API: `https://miniappapi.tbf.org.tr/webapi-service` (bkz. `scripts/tbf_config.json`)

Duyuru/erteleme bilgisi düzenli çekilebiliyorsa `tbf_sync.py`'ye bağla;
o zaman değişiklikler elle girilmeden yakalanır ve bildirim kendiliğinden
gider. Ayrıca **B maddesindeki sahte tarihlerin** gerçeği API'de başka bir
uçta duruyor olabilir — bulunursa `dateConfirmed` tahmini yerine gerçek
takvim kullanılır, bu en değerli düzeltme olur.

### D. Bekleyen

25 Eylül'deki 3. hafta maçı da üretilmiş dizinin içinde; gerçek gün/saati
öğrenilirse `data/u14/overrides.json`'a eklenmeli.

## Kurallar

- `data/<yaş>/overrides.json` elle girilen kesin bilgidir; senkronizasyon ezmez.
- Kesinleşmemiş tarihi veliye kesinmiş gibi gösterme.
- Ayrıntı: `evolog/README.md`, `deploy/README.md`.
