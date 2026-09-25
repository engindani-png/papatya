# Evolog U14 — kurulum ve işletme kılavuzu

Bu dosya sıfırdan kuranın ya da devralanın ihtiyaç duyduğu her şeyi içerir.
Son güncelleme: **18 Eylül 2026**.

---

## 1. Sistem neye benziyor

```
  GitHub (engindani-png/papatya, master)
        │  git
        ▼
  VDS 213.159.6.115 · /var/www/evolog
        │
        ├── evolog-sync.timer   (saat başı)
        │     1. git fetch + reset --hard origin/master
        │     2. scripts/tbf_sync.py --roster   → TBF'den veri + maç analizi
        │     3. server/evolog_push.py          → veli bildirimi
        │
        ├── evolog-api.service  (:8106, server/evolog_api.py)
        │     antrenman programı · yoklama · duyuru · abonelikler
        │
        └── nginx → evologsiyah.com
```

Uygulama saf statik (HTML/CSS/JS) + küçük bir Python API. Veritabanı
gerektiren tek parça yoklama ve duyuru kaydı (SQLite).

| | |
|---|---|
| Canlı adres | https://evologsiyah.com (eski `evolog.213-159-6-115.sslip.io` yönlendiriyor) |
| Depo | `github.com/engindani-png/papatya`, dal `master` |
| Yerel çalışma kopyası | `C:\Users\ENGIN\Desktop\Papatya` |
| VDS | `213.159.6.115`, SSH portu `23422`, kullanıcı `root` |
| Uygulama dizini | `/var/www/evolog` (git klonu) |
| Durum dizini | `/var/lib/evolog` (git ağacının **dışında**) |
| Antrenör şifresi | systemd `EVOLOG_ADMIN_PASS` (sunucuda tutulur — **bu depoya yazılmaz**) |

---

## 2. Dizin haritası

```
evolog/                 uygulama (PWA)
  index.html            kabuk: 5 sekme + antrenör paneli katmanı
  app.js                veli tarafının tamamı
  styles.css            tasarım değişkenleri ve bileşenler
  sw.js                 servis çalışanı (önbellek + push)
  manifest.webmanifest  PWA künyesi
  panel.css             antrenör paneli sayfalarının ortak biçimi
  panel-auth.js         panel girişi ve /api istekleri
  panel-analiz.js       ortak analiz hesapları (pozisyon, dört faktör, per-36)
  yoklama.html/.js      antrenör · yoklama + devamsızlık dökümü
  yonetim.html/.js      antrenör · antrenman programı
  parser.js             WhatsApp mesajı çözümleyici
  oyuncular.html/.js    antrenör · oyuncu gelişimi
  macanaliz.html/.js    antrenör · maç analizi
  rakip.html/.js        antrenör · rakip analizi
  duyuru.html/.js       antrenör · veliye bildirim
  logos/                TBF'den indirilen takım logoları

scripts/
  tbf_sync.py           TBF senkronu (fikstür, puan, kadro, logo, analiz)
  tbf_analiz.py         play-by-play → analiz dosyası
  test_tbf_analiz.py    41 test
  tbf_config.json       lig/takım kimlikleri, sezon
  local_edits.py        override uygulama + üretilmiş tarih tespiti
  yerel_guncelle.sh/.cmd

server/
  evolog_api.py         HTTP API (:8106)
  evolog_push.py        web push göndericisi
  attendance.py         yoklama + duyuru (SQLite)
  test_attendance.py    17 test

data/u14/
  league.json           fikstür, puan durumu, lig fikstürü, analiz listesi
  team.json             kadro ve teknik kadro
  overrides.json        elle girilen kesin maç bilgileri
  analiz/<macId>.json   maç analizi (nötr biçim, sürüm 4)

deploy/                 kurulum betikleri ve notlar
docs/                   tasarım, plan ve devir belgeleri
```

---

## 3. Sıfırdan kurulum

```bash
# VDS'te, root olarak
curl -fsSL https://raw.githubusercontent.com/engindani-png/papatya/master/deploy/kur.sh \
  | DOMAIN=evologsiyah.com bash
```

Script nginx + git kurar, depoyu klonlar, nginx ayarını yazar, Let's Encrypt
sertifikası alır.

Ardından elle yapılacaklar:

```bash
# 1. Bildirim için ayrı sanal ortam (sistem geneline pip ile kurma — certbot'u bozar)
python3 -m venv /opt/evolog-venv
/opt/evolog-venv/bin/pip install pywebpush

# 2. Senkron betiği ve zamanlayıcı
install -m 755 /var/www/evolog/deploy/evolog-sync.sh /usr/local/bin/evolog-sync.sh
systemctl enable --now evolog-sync.timer

# 3. API servisi
systemctl enable --now evolog-api

# 4. VAPID anahtarı (ilk çalıştırmada kendiliğinden üretilir)
EVOLOG_STATE_DIR=/var/lib/evolog /opt/evolog-venv/bin/python \
  /var/www/evolog/server/evolog_push.py --keys
```

### nginx'te dikkat edilecek üç kural

```nginx
# Antrenman programı git ağacında DEĞİL; durum dizininden servis edilir.
location ~ ^/data/(u14)/training\.json$ { alias /var/lib/evolog/training-$1.json; }

# Veri ve servis çalışanı asla önbelleğe alınmaz.
location /data/  { alias /var/www/evolog/data/; add_header Cache-Control "no-store"; }
location = /sw.js { add_header Cache-Control "no-store, must-revalidate"; }

location /api/ { proxy_pass http://127.0.0.1:8106; }
```

---

## 4. Servisler

| Birim | Ne yapar |
|---|---|
| `evolog-sync.timer` / `.service` | Saat başı: depoyu tazele → TBF'den çek → bildirim gönder |
| `evolog-api.service` | `server/evolog_api.py`, port 8106 |

```bash
systemctl status evolog-api evolog-sync.timer
journalctl -u evolog-sync -n 40 --no-pager      # son senkron
systemctl start evolog-sync                     # elle tetikle
```

Ortam değişkenleri (`evolog-api.service` içinde):
`EVOLOG_STATE_DIR=/var/lib/evolog` · `EVOLOG_ADMIN_PASS=<sunucuda tanımlı>` ·
`EVOLOG_PORT=8106` · `EVOLOG_DATA_DIR=/var/www/evolog/data`

> **Şifre buraya yazılmaz.** Depo herkese açık; buraya yazılan şifre
> yayınlanmış demektir. Değiştirmek için sunucuda:
>
> ```bash
> systemctl edit evolog-api          # EVOLOG_ADMIN_PASS=<yeni sifre>
> systemctl restart evolog-api
> ```

---

## 5. Durum dizini (`/var/lib/evolog`) — yedeklenecek tek yer

| Dosya | İçerik |
|---|---|
| `evolog.db` | **Yoklama ve duyuru kayıtları** (SQLite) |
| `training-u14.json` | Yayındaki antrenman programı |
| `subs.json` | Push abonelikleri |
| `notified.json` | Gönderilmiş bildirimler (tekrarı önler) |
| `vapid.json`, `vapid_private.pem` | Push anahtarları — **kaybolursa tüm abonelikler geçersiz olur** |

```bash
tar czf evolog-durum-$(date +%F).tgz -C /var/lib evolog
```

### Senkronun ÜRETTİĞİ dosyalar (`/var/www/evolog/data/<yaş>/`)

`league.json`, `team.json`, `drive_program.json`, `analiz/`, `analiz_eksik.json`
**git'te izlenmez.** Yedeklenmeleri şart değil: ilk senkron hepsini yeniden üretir.

> **Neden izlenmiyorlar:** deploy `git fetch + git reset --hard` yapıyor. İzlendikleri
> sürece her dağıtım canlı veriyi commit'teki eski hâline döndürüyordu. 24 Eylül
> 2026'da gerçekten zarar verdi: 4 Ekim maçının saati ve salonu Drive'dan düzeldi,
> velilere bildirim gitti, sonraki deploy maçı yeniden 8 Aralık yaptı — bildirimde
> bir tarih, uygulamada başkası. Bu dosyalar **çıktıdır, kaynak değil.**
> Elle tutulan `overrides.json` ve `venues.json` izlenmeye devam eder.

---

## 6. API uçları

Hepsi `Authorization: Bearer <şifre>` ister (health ve push/key hariç).

| Uç | Ne |
|---|---|
| `GET /api/health` | Sağlık |
| `GET/POST /api/training` | Antrenman programı |
| `GET/POST /api/attendance` | Yoklama kaydı |
| `GET /api/attendance/summary` | Devam özeti |
| `GET /api/attendance/player?key=` | Bir oyuncunun devamsızlık dökümü |
| `GET/POST /api/duyuru` | Duyuru gönder / geçmiş |
| `POST /api/auth` | Şifre doğrula |
| `GET /api/push/key`, `POST /api/push/subscribe` | Web push |

---

## 7. TBF verisi

Taban: `https://miniappapi.tbf.org.tr/webapi-service` (kimlik doğrulama yok).
Ayrıntılı uç listesi ve tuzaklar için `docs/` ve `scripts/tbf_sync.py` başlığı.

**Bilinmesi gereken üç şey:**

1. **Yer tutucu tarihler.** TBF ilan edilmemiş maçlar için gerçek tarih yerine
   dolgu döndürüyor (aynı haftanın tüm maçları aynı gün+saat). `local_edits.py`
   bunları `dateConfirmed=false` işaretler; uygulama o maçlarda saat basmaz ve
   geri sayım yapmaz. Kesin bilgi `data/u14/overrides.json`'a yazılır.
2. **Atış koordinatı aynalama.** `x > 50` ise `100 - x`. "3-4. çeyreği aynala"
   kuralı yalnız ev sahibi için doğrudur, deplasmanın atışlarını yanlış yarıya
   koyar.
3. **Analiz dosyası sürümü.** `tbf_analiz.ANALIZ_SURUM` artırılırsa senkron
   eski dosyaları kendiliğinden yeniden üretir. Çalışma başına en fazla
   `ANALIZ_LIMIT` (10) yeni maç çekilir.

---

## 8. Sık yapılan işler

**Antrenman programı girme:** Uygulama → Takım → Antrenör paneli → Program.
Depodaki bir dosyayı düzenlemek işe yaramaz (nginx durum dizinine bakıyor).

**Maç tarihi düzeltme:** `data/u14/overrides.json` → commit → push. Senkron
bunu asla ezmez ve velilere değişiklik bildirimi kendiliğinden gider.

**Elle bildirim:**
```bash
EVOLOG_STATE_DIR=/var/lib/evolog /opt/evolog-venv/bin/python \
  /var/www/evolog/server/evolog_push.py --duyuru "Metin" --baslik "Başlık"
```

**Testler:**
```bash
python -m unittest scripts.test_tbf_analiz server.test_attendance   # 58 test
```

**Yayına alma:** `git push` → VDS saat başı çeker. Acele varsa:
```bash
ssh -p 23422 root@213.159.6.115 \
  'cd /var/www/evolog && git fetch -q origin && git reset -q --hard origin/master'
```

⚠️ Arayüz dosyası değiştiyse `evolog/sw.js` içindeki `CACHE` sürümünü artır,
yoksa telefonlardaki kopya eski kalır.

---

## 9. Bilinen tuzaklar

- **pip3 ile sistem geneline kurulum yapma.** `pywebpush`'un istediği
  cryptography, certbot'un pyOpenSSL'ini bozar ve sunucudaki tüm sertifika
  yenilemeleri riske girer. Push ayrı venv'de çalışır.
- **VAPID anahtarı metin olarak verilmez.** `pywebpush(vapid_private_key=...)`
  parametresine PEM metni verilirse `py_vapid` çöker; **dosya yolu** verilmeli.
  Bildirimler haftalarca bu yüzden gitmedi.
- **`/api/` servis çalışanından geçmez.** Önbelleğe girerse antrenör kaydettiği
  programı eski haliyle görür.
- **`data/u14/training.json` depoda durmaz.** nginx durum dizinine bakar;
  depodaki kopya yayına girmez ve `git reset --hard` onu siler.
- **`.overlay` kuralına `display:flex` verme.** `hidden` özniteliğini ezer,
  katman hep açık kalır. `styles.css`'teki `[hidden]{display:none!important}`
  silinmemeli.
- **`data/<yaş>/league.json` ve arkadaşlarını git'e geri ekleme.** Deploy
  `reset --hard` yaptığı için canlı veri commit'teki hâline döner (yukarı bak).
- **`notified.json`'u silme.** Hangi bildirimin gönderildiğini tutar; kaybolursa
  geçmiş maç sonuçları ve duyurular velilere **yeniden** gider.
- **Bildirim türü eklerken `evolog_push.olay_turu()`'ne önek ekle.** Bilinmeyen
  olay "mac" sayılır; eklemezsen yeni bildirim türünü kapatan veli onu
  kapatamaz ya da yanlış grupta bulur.
- **Drive eşleştirmesinde "emniyet" kuralı eklerken dikkat.** 25 Eylül 2026'da
  üç ayrı kural federasyonun resmî programını fiilen bloke ediyordu: `(A)/(B)`
  ekini birebir tutma şartı, sahiplik kontrolünün eki karşılaştırması ve TBF
  tarihine ±10 gün penceresi. Kural: Drive **her zaman** TBF'yi ezmeli; eşleşmeyi
  zorlaştıran hiçbir şey bunu engellememeli.

---

## 9b. Bildirimler — kısa özet

| Tür | Ne kapsar | Başlık |
|---|---|---|
| `koc` | Antrenörün duyuruları, antrenman programı değişikliği | 🔥 |
| `mac` | Kendi maçımız: sonuç, gün/saat/salon değişikliği, 4 saat kala hatırlatma | 🏀 MAÇ DUYURUSU |
| `lig` | Ligdeki diğer takımların sonuçları (tek bildirimde toplanır) | 📣 LİG SONUCU |

- Abone tercihi `subs.json` → `turler`. **Alan yoksa hepsi açık** (eski abonelikler
  bildirim kaybetmesin).
- **Sessiz saat 22:00–07:00**: otomatik bildirim gönderilmez ve *işaretlenmez*,
  pencere bitince ilk turda gider. İnsan kararıyla aşmak için `--sessizi-atla`.
- Elle maç duyurusu: `evolog_push.py --mac-duyurusu "METİN" [--mac-id <id>]`.
- Telefona gelen **her** bildirim cihazda arşivlenir (`evolog/duyuru-arsiv.js`,
  IndexedDB). `sw.js` ve `app.js` aynı dosyayı yükler — şemaları ayrışmasın diye.

---

## 9c. Kendi kendini denetleme

Senkron her turda şunları yazar (`journalctl -u evolog-sync`):

- `Analiz BOS: ...` — TBF istatistiği henüz yayınlamamış; 3 saatte bir yeniden
  denenir, maç 45 günden eskiyse bırakılır. Liste: `data/<yaş>/analiz_eksik.json`.
- `DIKKAT: N takimda puan durumu ile fikstur ortusmuyor` — federasyon iki ayrı
  kaynaktan veri veriyor; biri güncellenip öteki unutulmuş olabilir.
- `drive DIKKAT BIZIM MACIMIZ: ...` — Drive satırı bizim maçımız ama eşleşmedi;
  resmî salon/saat uygulamaya gelmiyor demektir.
- `N ertelenmis mac isaretlendi` — haftası oynanmış ama kendisi 7+ gün ileride.

---

## 10. Sıradaki iş

Veli üyelik sistemi: tasarımı onaylı (`docs/superpowers/specs/2026-09-15-uyelik-sistemi-design.md`),
kodu yazılmadı. SQLite tabanı (`evolog.db`) ve yoklama bu sistemi bekleyecek
şekilde kuruldu; devam yüzdesinin veliye açılması da ona bağlı.
