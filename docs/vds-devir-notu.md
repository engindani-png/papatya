# VDS durum notu — 17 Eylül 2026 (akşam)

Bulut oturumunun bıraktığı devir notu, yerel CLI oturumunda uygulandı.
Aşağıdaki maddeler **yapıldı**; sonda açık kalanlar var.

## Sistem

| | |
|---|---|
| Repo | `github.com/engindani-png/papatya`, dal `master` |
| Canlı site | https://evologsiyah.com/evolog/ · https://evolog.213-159-6-115.sslip.io/evolog/ |
| VDS | `213.159.6.115` · uygulama `/var/www/evolog` · durum `/var/lib/evolog` |
| Zamanlayıcı | `evolog-sync.timer` — saat başı: `git reset --hard origin/master` → `tbf_sync.py` → `evolog_push.py` |
| Kullanıcılar | Veliler. PWA olarak telefonlarına kurulu. 9 abone. |

Zinciri yürüten script: `deploy/evolog-sync.sh` (VDS'te `/usr/local/bin/evolog-sync.sh`).

## A. Bildirimler — ÇÖZÜLDÜ

Devir notundaki teşhis ("cron yalnızca git pull yapıyordu, push hiç
çalıştırılmadı") **yanlıştı**: `evolog-sync.sh` bildirim betiğini saat başı
zaten çağırıyordu. Bildirimlerin gitmemesinin gerçek sebebi bir kod hatası:

```
ValueError: Could not deserialize key data ... ASN.1 parsing error: invalid length
```

`pywebpush`'a VAPID özel anahtarı **PEM metni** olarak veriliyordu; `py_vapid`
metni ham DER sanıp her abonede çöküyordu. Sunucuda ölçüldü:
`Vapid.from_string(pem)` → hata, `Vapid.from_file(yol)` → OK. Anahtar artık
dosya yolu olarak geçiliyor (commit `78ff0ed`).

İkinci hata: gönderim başarısız olsa bile olay `notified.json`'a "gönderildi"
yazılıyordu, yani hata kalıcı oluyordu. Artık yalnızca en az bir aboneye
ulaşan olay işaretleniyor.

**Sonuç:** 17 Eylül 19:00'da maç değişikliği bildirimi **9 aboneye gitti**,
1 geçersiz abonelik listeden düşürüldü.

> `deploy/bildirim_kur.sh` çalıştırılmadı: 5 dakikalık ikinci bir cron,
> `evolog-sync.timer` ile aynı `notified.json` üzerinde yarışırdı. Script
> artık timer'ı görürse cron yazmıyor, yalnızca durum raporluyor.

## B. Canlı doğrulama — TAMAM

| Kontrol | Sonuç |
|---|---|
| `sw.js` | `CACHE = "evolog-v16"` (her iki alan adında) |
| `data/u14/league.json` → 346858 | `2026-09-23 20:00`, `dateConfirmed: true` |
| Kesinleşmemiş maç | 20 (her üç yaş grubunda da 20/22) |

VDS'in bir süre eski veri göstermesinin sebebi arıza değildi: commit'ler
18:22–18:31'de push'landı, son senkron 18:10'daydı. `git fetch` sağlıklı.

## C. Duyurunun kaynağı — TBF'de yok (araştırma tamamlandı)

TBF'nin Nuxt paketinden **tüm API uçları** çıkarılıp denendi. Erteleme/duyuru
verisi hiçbirinde yok:

| Uç | Sonuç |
|---|---|
| `Team/get-team-detail-matches-by-season-and-league` | 346858 → hâlâ `2026-10-03T18:30` |
| `Match/mac-header?matchId=346858` | aynı tarih; duyuru alanı yok |
| `Altyapilar/news`, `Altyapilar/news-details` | boş liste |
| `Altyapilar/matches` | filtreleri yok sayıyor, sabit 20 kayıtlık vitrin |
| `Match/get-daily-matches`, `Match/get-all-matches-for-filter` | yerel lig için boş |
| `Match/tarih-mac-sayisi` | yalnız üst ligleri sayıyor (14 Eylül'deki maçımız yok) |

**Yer tutucu imzası düzeltildi.** Lig genelindeki 132 maç incelendi:

- 1. ve 2. hafta maçlarının saatleri maç maç farklı (11:30 / 16:00 / 18:00 /
  20:00) → bunlar **gerçek, ilan edilmiş** tarihler.
- 3. haftadan itibaren haftanın **altı maçı da aynı gün ve aynı saatte**
  (25 Eylül 18:30 gibi) → yer tutucu.

Yani dolgunun asıl imzası "aynı haftanın tüm maçları aynı gün+saat".
`scripts/local_edits.py` takım bazlı 9 gün + aynı saat kuralını kullanıyor;
u14/u16/u18'de aynı sonucu veriyor (20/22), ama lig geneline bakan kural daha
sağlam olur — ileride iyileştirilebilir.

**Çelişki (kullanıcıya bildirildi):** TBF, 346858 için hâlâ *3 Ekim 18:30*
diyor; kulüpten gelen bilgi *23 Eylül 20:00*. Velilere kulüp bilgisi gönderildi
(`overrides.json` kesin bilgidir). TBF kaydını sonradan düzeltirse senkron
bunu görür; override durduğu sürece velilere yanlış tarih gitmez.

**İyi haber:** TBF bir maçın gerçek tarihini yayınladığında API'de görünüyor
(1. ve 2. hafta böyle). Değişiklik bildirimi artık çalıştığı için, elle
girmeye gerek kalmadan velilere kendiliğinden gidecek.

## D. Açık kalanlar

1. **25 Eylül (3. hafta, `346867`)** — TBF'de hâlâ yer tutucu (25 Eylül 18:30,
   ligin altı maçı da aynı saatte). Kulüpten kesin gün/saat gelince
   `data/u14/overrides.json`'a eklenmeli; bildirim kendiliğinden gider.
2. `346858` için TBF kaydı 3 Ekim'de kalırsa kulüple teyit edilmeli.

## Kurallar

- `data/<yaş>/overrides.json` elle girilen kesin bilgidir; senkronizasyon ezmez.
- Kesinleşmemiş tarihi veliye kesinmiş gibi gösterme.
- Ayrıntı: `evolog/README.md`, `deploy/README.md`.
