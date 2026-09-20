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


def main() -> int:
    yeni = uret()
    if "--check" in sys.argv:
        mevcut = HEDEF.read_text(encoding="utf-8") if HEDEF.exists() else ""
        if mevcut == yeni:
            print("demo/app.js guncel.")
            return 0
        print("demo/app.js SAPMIS - 'python3 scripts/demo_sync.py' calistirin.")
        return 1
    HEDEF.write_text(yeni, encoding="utf-8")
    print(f"Yazildi: {HEDEF.relative_to(ROOT)}  ({len(yeni.splitlines())} satir)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
