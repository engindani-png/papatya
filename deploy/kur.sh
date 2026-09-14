#!/usr/bin/env bash
# Evolog U14 uygulamasini bir VDS'e kurar (Ubuntu/Debian).
#
# VDS'te root olarak tek satir:
#   curl -fsSL https://raw.githubusercontent.com/engindani-png/papatya/master/deploy/kur.sh | bash
#
# Alan adi varsa (HTTPS sertifikasi da alinir):
#   curl -fsSL .../kur.sh | DOMAIN=takim.ornek.com bash
#
# Kurduktan sonra site: http://<VDS-IP>/  (kok adres uygulamaya yonlendirir)

set -euo pipefail

REPO="${REPO:-https://github.com/engindani-png/papatya.git}"
DIR="${DIR:-/var/www/evolog}"
BRANCH="${BRANCH:-master}"
DOMAIN="${DOMAIN:-}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Bu script root yetkisi istiyor:  sudo bash kur.sh" >&2
  exit 1
fi

echo "==> Paketler kuruluyor (nginx, git)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx git

echo "==> Uygulama indiriliyor -> $DIR"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch -q origin "$BRANCH"
  git -C "$DIR" reset -q --hard "origin/$BRANCH"
else
  rm -rf "$DIR"
  git clone -q --depth 1 --branch "$BRANCH" "$REPO" "$DIR"
fi
chown -R www-data:www-data "$DIR"

echo "==> nginx ayarlaniyor"
cat > /etc/nginx/sites-available/evolog <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN:-_};

    root $DIR;
    index index.html;

    # Kok adres dogrudan takim uygulamasina gitsin (veliler icin kisa link)
    location = / { return 302 /evolog/; }

    # Veri dosyalari onbelleklenmesin ki yeni skorlar hemen gorunsun
    location /data/ {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        try_files \$uri =404;
    }

    location / {
        try_files \$uri \$uri/ =404;
    }

    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml text/html;
}
NGINX

ln -sf /etc/nginx/sites-available/evolog /etc/nginx/sites-enabled/evolog
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
systemctl enable -q nginx

echo "==> Otomatik guncelleme (5 dakikada bir depodan ceker)"
cat > /etc/cron.d/evolog <<CRON
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
*/5 * * * * root cd $DIR && git fetch -q origin $BRANCH && git reset -q --hard origin/$BRANCH && chown -R www-data:www-data $DIR
CRON
chmod 644 /etc/cron.d/evolog

if [ -n "$DOMAIN" ]; then
  echo "==> HTTPS sertifikasi aliniyor ($DOMAIN)"
  apt-get install -y -qq certbot python3-certbot-nginx
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect || {
    echo "!! Sertifika alinamadi. Alan adinin bu sunucuya yonlendigini kontrol edip tekrar deneyin:"
    echo "   certbot --nginx -d $DOMAIN"
  }
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "================================================"
echo " Kurulum tamam."
if [ -n "$DOMAIN" ]; then
  echo " Velilerle paylasin:  https://$DOMAIN/"
else
  echo " Velilerle paylasin:  http://${IP:-<VDS-IP>}/"
fi
echo
echo " Veri guncelleme: kendi bilgisayarinizda depo klasorunde"
echo "   ./scripts/yerel_guncelle.sh"
echo " calistirin; VDS 5 dakika icinde yeni veriyi ceker."
echo "================================================"
