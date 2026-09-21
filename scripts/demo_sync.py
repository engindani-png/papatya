#!/usr/bin/env python3
"""evolog/app.js -> evolog/demo/app.js  (demoya ozgu iki yamayi uygulayarak)

Demo, ana uygulamanin birebir kopyasi uzerinde yalnizca GORUNUMU dener.
Kodu elle kopyalamak sapmaya aciktir; bu script farki tek komutta kapatir:

    python3 scripts/demo_sync.py            # yaz
    python3 scripts/demo_sync.py --check    # yazmadan denetle (cikis 1 = sapma)

Iki yama:
  1. Servis calisani kaydi cikarilir — demo PWA olarak kurulmaz ve ana
     uygulamanin onbellegine karismaz.
  2. logoUrl(): league.json'daki logo yollari ana uygulamanin derinligine
     gore yazilmis; demo bir seviye asagida oldugu icin calisma aninda
     hesaplanan tabana baglanir.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
KAYNAK = ROOT / "evolog" / "app.js"
HEDEF = ROOT / "evolog" / "demo" / "app.js"

# 21 Eylul 2026: yeni gorunum (skin.css) ANA uygulamaya alindi. Eskisine
# donulebilsin diye /klasik/ altinda skin'siz bir kopya yayinlaniyor. Elle
# kopyalamak yine sapmaya acik oldugu icin o da buradan uretilir.
KLASIK_DIZIN = ROOT / "evolog" / "klasik"
DEMO_INDEX = ROOT / "evolog" / "demo" / "index.html"

# klasik/index.html = demo/index.html eksi yeni gorunumun iki satiri
KLASIK_CIKAR = (
    '<link rel="stylesheet" href="../skin.css">\n',
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
    '&family=Space+Grotesk:wght@400;500&family=JetBrains+Mono:wght@400&display=swap">\n',
)

SW_BAS = '  if ("serviceWorker" in navigator && !INLINE) {'
SW_YERINE = "  // DEMO: servis calisani kaydi yok - ana uygulamanin onbellegine karismasin.\n"

LOGO_ESKI = """  function teamLogo(src, size) {
    if (!src) return "";
    return '<img class="lg' + (size ? " " + size : "") + '" src="' + esc(src) +"""

LOGO_YENI = """  /* DEMO: league.json'daki logo yollari ana uygulamanin derinligine gore
     yazilmis. Demo bir seviye asagida oldugu icin calisma aninda hesaplanan
     tabana baglanir. */
  function logoUrl(src) {
    if (!src) return "";
    var taban = window.EVOLOG_ASSET_BASE || "";
    return taban ? src.replace(/^(\\.\\.\\/)*evolog\\//, taban) : src;
  }

  function teamLogo(src, size) {
    if (!src) return "";
    return '<img class="lg' + (size ? " " + size : "") + '" src="' + esc(logoUrl(src)) +"""


def blok_sonu(s: str, bas: int) -> int:
    """bas konumundaki '{' ile eslesen '}' sonrasini verir."""
    derinlik, i = 0, bas
    while i < len(s):
        if s[i] == "{":
            derinlik += 1
        elif s[i] == "}":
            derinlik -= 1
            if derinlik == 0:
                return i + 1
        i += 1
    raise ValueError("kapanmayan blok")


def uret() -> str:
    s = KAYNAK.read_text(encoding="utf-8")

    if SW_BAS not in s:
        raise SystemExit("HATA: servis calisani blogu bulunamadi; app.js degismis olabilir.")
    bas = s.index(SW_BAS)
    s = s[:bas] + SW_YERINE + s[blok_sonu(s, bas):]

    if LOGO_ESKI not in s:
        raise SystemExit("HATA: teamLogo blogu bulunamadi; app.js degismis olabilir.")
    s = s.replace(LOGO_ESKI, LOGO_YENI, 1)
    return s


def klasik_index() -> str:
    """demo/index.html'den yeni gorunumun satirlarini cikararak uretir."""
    s = DEMO_INDEX.read_text(encoding="utf-8")
    for satir in KLASIK_CIKAR:
        if satir not in s:
            raise SystemExit(f"HATA: demo/index.html'de beklenen satir yok:\n  {satir.strip()}")
        s = s.replace(satir, "", 1)
    # Yol cozumleme betigi klasorunu ad olarak ariyor; kopyada da kendi
    # klasorunu aramali, yoksa taban yanlis hesaplanip logolar kiriliyor.
    if '"/demo/"' not in s:
        raise SystemExit('HATA: demo/index.html icinde "/demo/" yol isareti yok.')
    s = s.replace('"/demo/"', '"/klasik/"')
    return s.replace("DEMO · Evolog", "KLASİK · Evolog", 1)


def main() -> int:
    yeni = uret()
    kl_index = klasik_index()
    hedefler = [(HEDEF, yeni),
                (KLASIK_DIZIN / "app.js", yeni),
                (KLASIK_DIZIN / "index.html", kl_index)]

    if "--check" in sys.argv:
        sapan = [y for y, icerik in hedefler
                 if (y.read_text(encoding="utf-8") if y.exists() else "") != icerik]
        if not sapan:
            print("demo/ ve klasik/ guncel.")
            return 0
        for y in sapan:
            print(f"{y.relative_to(ROOT)} SAPMIS - 'python3 scripts/demo_sync.py' calistirin.")
        return 1

    KLASIK_DIZIN.mkdir(parents=True, exist_ok=True)
    for yol, icerik in hedefler:
        yol.write_text(icerik, encoding="utf-8")
        print(f"Yazildi: {yol.relative_to(ROOT)}  ({len(icerik.splitlines())} satir)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
