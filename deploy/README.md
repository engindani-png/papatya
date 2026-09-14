# Yayına alma

Uygulama tamamen statik (HTML/CSS/JS + JSON veri). Veritabanı, PHP, Node
gerekmez — herhangi bir web sunucusu yeter.

## Nasıl çalışıyor

```
  Sizin bilgisayarınız                GitHub                    VDS
  ────────────────────                ──────                    ───
  yerel_guncelle.sh                                      nginx (siteyi yayınlar)
  → TBF'den çeker         ──push──▶  data/league.json  ──▶ cron her 5 dk'da
  (Türkiye bağlantısı)                                      git pull yapar
```

Veriyi **sizin bilgisayarınız** çeker, çünkü TBF veri merkezi IP'lerini
403 ile engelliyor (ölçüldü: GitHub Actions'tan hem düz HTTP hem gerçek
Chromium reddedildi). VDS yalnızca siteyi yayınlar — orada TBF'ye istek
atılmaz, dolayısıyla engel sorun olmaz.

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

TBF'den çeker, `data/league.json` dosyasını günceller, commit'leyip
push'lar. VDS 5 dakika içinde, GitHub Pages ise hemen yeni veriyi gösterir.

## Kendi bilgisayarınızda Claude Code

Bu depoyu kendi bilgisayarınıza indirip klasörde `claude` komutunu
çalıştırırsanız, oradaki oturum hem TBF'ye erişebilir (Türkiye bağlantısı)
hem de VDS'inize bağlanabilir — bu web oturumunun ikisini de yapamamasının
sebebi, Anthropic bulutunda kısıtlı ağla çalışıyor olması.

## Veliler için

Link telefonda açılır. Tarayıcı menüsünden **“Ana ekrana ekle”** dendiğinde
uygulama kendi ikonuyla, tam ekran açılır ve çevrimdışı da çalışır.
