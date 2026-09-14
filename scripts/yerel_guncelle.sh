#!/usr/bin/env bash
# TBF verisini KENDI bilgisayarinizdan ceker ve repoya gonderir.
#
# TBF, veri merkezi IP'lerini (GitHub Actions dahil) 403 ile engelliyor;
# normal bir Turkiye baglantisindan ise sayfalar acilabiliyor. Bu script
# tam olarak bunu yapar: sizin baglantinizdan ceker, sonucu repoya isler.
#
#   ./scripts/yerel_guncelle.sh              -> cek, commit'le, push'la
#   ./scripts/yerel_guncelle.sh --dry-run    -> sadece dene, hicbir sey yazma
#   ./scripts/yerel_guncelle.sh --probe      -> adresleri dene, ne geldigini yaz

set -euo pipefail
cd "$(dirname "$0")/.."

echo "TBF verisi cekiliyor..."
python3 scripts/tbf_sync.py "$@"

# --dry-run / --probe modlarinda repoya dokunma
for arg in "$@"; do
  case "$arg" in
    --dry-run|--probe) exit 0 ;;
  esac
done

if git diff --quiet -- data/league.json; then
  echo "Degisiklik yok, gonderilecek bir sey yok."
  exit 0
fi

git add data/league.json
git commit -m "TBF verisi guncellendi ($(date '+%Y-%m-%d %H:%M'))"

branch="$(git rev-parse --abbrev-ref HEAD)"
for i in 1 2 3 4; do
  if git push -u origin "$branch"; then
    echo "Gonderildi. Uygulama birkac dakika icinde guncel veriyi gosterecek."
    exit 0
  fi
  echo "Push basarisiz, tekrar deneniyor..."
  sleep $((2 ** i))
done
echo "Push edilemedi; baglantiyi kontrol edip tekrar deneyin." >&2
exit 1
