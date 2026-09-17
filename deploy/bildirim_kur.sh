#!/usr/bin/env bash
# Mac bildirimlerini VDS'te zamanlar ve bekleyenleri hemen gonderir.
#
# VDS'te root olarak:
#   bash /var/www/evolog/deploy/bildirim_kur.sh
#
# Yalnizca zamanlayici YOKSA gereklidir. Mevcut VDS'te bildirim zaten
# evolog-sync.timer icinde (saat basi) calisiyor; o durumda bu script cron
# YAZMAZ, sadece durumu raporlar. Iki zamanlayici ayni anda calisirsa
# notified.json uzerinde yarisirlar.
# evolog_push.py gonderdigi her olayi notified.json'a yazar, ayni bildirim
# ikinci kez gitmez - zamanlayici guvenle sik calisabilir.

set -euo pipefail

DIR="${DIR:-/var/www/evolog}"
STATE="${EVOLOG_STATE_DIR:-/var/lib/evolog}"
PUSH="$DIR/server/evolog_push.py"

if [ "$(id -u)" -ne 0 ]; then
  echo "Root gerekiyor:  sudo bash $0" >&2
  exit 1
fi

[ -f "$PUSH" ] || { echo "Bulunamadi: $PUSH" >&2; exit 1; }

# pywebpush hangi python'da varsa onu kullan; yoksa sisteme kur.
PY=""
for cand in "$DIR/venv/bin/python3" /opt/evolog/venv/bin/python3 python3; do
  if command -v "$cand" >/dev/null 2>&1 || [ -x "$cand" ]; then
    if "$cand" -c "import pywebpush" >/dev/null 2>&1; then PY="$cand"; break; fi
  fi
done
if [ -z "$PY" ]; then
  echo "==> pywebpush kuruluyor"
  python3 -m pip install --quiet --break-system-packages pywebpush 2>/dev/null \
    || python3 -m pip install --quiet pywebpush
  PY="python3"
fi
echo "==> Python: $PY"

mkdir -p "$STATE"

echo "==> Durum"
EVOLOG_STATE_DIR="$STATE" "$PY" "$PUSH" --status || true

# Zaten zamanlanmis mi? (VDS'teki kurulum: evolog-sync.timer saat basi
# depoyu tazeler, TBF'den ceker ve bildirimi gonderir.)
if systemctl is-enabled evolog-sync.timer >/dev/null 2>&1; then
  echo
  echo "evolog-sync.timer kurulu: bildirim saat basi zaten gonderiliyor."
  echo "Ikinci bir zamanlayici kurulmadi. Bekleyenleri simdi gondermek icin:"
  echo "  systemctl start evolog-sync"
  exit 0
fi

echo
echo "==> Cron kuruluyor (5 dakikada bir)"
cat > /etc/cron.d/evolog-bildirim <<CRON
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
EVOLOG_STATE_DIR=$STATE
*/5 * * * * root $PY $PUSH >> /var/log/evolog-bildirim.log 2>&1
CRON
chmod 644 /etc/cron.d/evolog-bildirim

echo "==> Bekleyen bildirimler simdi gonderiliyor"
EVOLOG_STATE_DIR="$STATE" "$PY" "$PUSH"

echo
echo "Tamam. Bundan sonra gun/saat degisikligi, mac sonucu ve mac hatirlatmasi"
echo "5 dakika icinde kendiliginden gidecek. Kayit: /var/log/evolog-bildirim.log"
