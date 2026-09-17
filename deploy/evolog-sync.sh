#!/usr/bin/env bash
# VDS'te /usr/local/bin/evolog-sync.sh olarak durur; evolog-sync.timer saat
# basi calistirir (systemd unit'leri asagida). Bu dosya o scriptin depodaki
# kopyasidir - sunucuda degistirirseniz buraya da isleyin.
#
#   /etc/systemd/system/evolog-sync.service  -> ExecStart=/usr/local/bin/evolog-sync.sh
#   /etc/systemd/system/evolog-sync.timer    -> OnUnitActiveSec=1h, Persistent=true
#
# Zincir: depoyu tazele -> TBF'den cek -> degisen/biten mac icin bildirim gonder.
#
# Bildirim betigi kendi sanal ortaminda calisir: pywebpush'un istedigi guncel
# cryptography, sistemdeki certbot'un pyOpenSSL'ini bozuyor.
set -uo pipefail
ROOT="/var/www/evolog"
cd "$ROOT" || exit 1

# Hata ciktisi bastirilmaz: sessiz basarisiz bir fetch, sitenin gunlerce eski
# veri gostermesi demek olur ve journalctl'de hicbir iz birakmaz.
git fetch -q origin && git reset -q --hard origin/master

EVOLOG_LOGO_DIR="$ROOT/evolog/logos" EVOLOG_LOGO_URL="/logos" \
  python3 scripts/tbf_sync.py --roster

EVOLOG_STATE_DIR=/var/lib/evolog \
EVOLOG_APP_URL="https://evologsiyah.com/" \
  /opt/evolog-venv/bin/python server/evolog_push.py
