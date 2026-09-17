# Yayına alma

Uygulama tamamen statik (HTML/CSS/JS + JSON veri). Veritabanı, PHP, Node
gerekmez — herhangi bir web sunucusu yeter.

## Nasıl çalışıyor

```
  GitHub (kaynak kod)              VDS 213.159.6.115
  ───────────────────              ─────────────────
  master dalı        ──git──▶  evolog-sync.timer (saatte bir)
                                 1. git fetch + reset --hard origin/master
                                 2. scripts/tbf_sync.py  → TBF'den veri
                                 3. server/evolog_push.py → veli bildirimi
                                        │
                                   nginx /var/www/evolog
```

Zinciri `deploy/evolog-sync.sh` yürütür; VDS'te `/usr/local/bin/evolog-sync.sh`
olarak durur ve `evolog-sync.timer` saat başı tetikler. **TBF'ye VDS'ten
erişiliyor** (ölçüldü, 17 Eylül 2026: `miniappapi.tbf.org.tr` sunucudan
sorunsuz yanıt veriyor) — veriyi çekmek için ev bilgisayarı gerekmiyor.
Yalnızca kod değişikliği push'lanır; veri dosyalarını sunucu kendisi üretir.

Durum dosyaları (abonelikler, gönderilmiş bildirimler, VAPID anahtarı)
`/var/lib/evolog` altındadır ve depoya girmez.

## Seçenek 1 — VDS (kendi sunucunuz)

VDS'e root ile bağlanıp tek satır:

```bash
curl -fsSL https://raw.githubusercontent.com/engindani-png/papatya/master/deploy/kur.sh | bash
```

Alan adınız varsa (HTTPS sertifikası da alınır):

```bash
curl -fsSL https://raw.githubusercontent.com/engindani-png/papatya/master/deploy/kur.sh | DOMAIN=takim.ornek.com bash
```

Script şunları yapar: nginx + git kurar, depoyu `/var/www/evolog` altına
klonlar, nginx ayarını yazar (kök adres `/evolog/` sayfasına yönlendirir,
`data/` önbelleklenmez), her 5 dakikada depodan güncelleyen bir cron
kurar, alan adı verildiyse Let's Encrypt sertifikası alır.

Bitince veliler için link: `http://<VDS-IP>/` veya `https://<alan-adınız>/`

## Seçenek 2 — GitHub Pages (sunucu gerekmez, ücretsiz)

Depo → **Settings → Pages** → Source: `Deploy from a branch`,
Branch: `master`, klasör: `/ (root)` → **Save**.

Birkaç dakika sonra: `https://engindani-png.github.io/papatya/evolog/`

HTTPS hazır gelir, bakım gerektirmez. Veri güncellemesi push'la birlikte
otomatik yayına girer.

## Veriyi güncelleme

Maçtan sonra, depo klasöründe:

```bash
./scripts/yerel_guncelle.sh          # Windows: scripts\yerel_guncelle.cmd
```

TBF'den çeker, `data/<yaş>/league.json` dosyalarını günceller, commit'leyip
push'lar. Normalde gerekmez: VDS zaten saat başı kendisi çekiyor. GitHub
Pages kullanıyorsanız veri ancak bu yolla güncellenir.

Maç günü/saati kulüpten kesin olarak bildirildiyse `data/<yaş>/overrides.json`
dosyasına yazın; senkronizasyon bunu asla ezmez ve değişiklik velilere
bildirim olarak gider.

## Kendi bilgisayarınızda Claude Code

Bu depoyu kendi bilgisayarınıza indirip klasörde `claude` komutunu
çalıştırırsanız, oradaki oturum hem TBF'ye erişebilir (Türkiye bağlantısı)
hem de VDS'inize bağlanabilir — bu web oturumunun ikisini de yapamamasının
sebebi, Anthropic bulutunda kısıtlı ağla çalışıyor olması.

## Veliler için

Link telefonda açılır. Tarayıcı menüsünden **“Ana ekrana ekle”** dendiğinde
uygulama kendi ikonuyla, tam ekran açılır ve çevrimdışı da çalışır.
