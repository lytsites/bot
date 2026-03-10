#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

BASE_DOMAIN="${1:-}"
FRONTEND_HOST="${2:-}"
APP_DIR="${APP_DIR:-/opt/tg-web-auth}"
APP_USER="${APP_USER:-tgapp}"
APP_GROUP="${APP_GROUP:-tgapp}"

if [[ -z "$BASE_DOMAIN" ]]; then
  echo "Usage: $0 <base-domain> [frontend-host]"
  echo "Example: $0 example.com app.example.com"
  exit 1
fi

if [[ -z "$FRONTEND_HOST" ]]; then
  FRONTEND_HOST="$BASE_DOMAIN"
fi

if [[ ! -d "$APP_DIR" ]]; then
  echo "Directory not found: $APP_DIR"
  echo "Clone repo first, for example:"
  echo "  git clone <repo-url> $APP_DIR"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  git \
  nginx \
  python3 \
  python3-venv \
  python3-pip \
  nodejs \
  npm

if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node -v | sed -E 's/^v([0-9]+).*/\1/')"
else
  NODE_MAJOR="0"
fi

if [[ "$NODE_MAJOR" -lt 18 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y --no-install-recommends nodejs
fi

if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --shell /bin/bash "$APP_USER"
fi

if ! getent group "$APP_GROUP" >/dev/null 2>&1; then
  groupadd --system "$APP_GROUP"
fi

usermod -a -G "$APP_GROUP" "$APP_USER" || true
chown -R "$APP_USER:$APP_GROUP" "$APP_DIR"

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  chown "$APP_USER:$APP_GROUP" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "Created $APP_DIR/.env from .env.example. Fill real secrets before go-live."
fi

sudo -u "$APP_USER" bash -lc "cd '$APP_DIR' && python3 -m venv .venv"
sudo -u "$APP_USER" bash -lc "cd '$APP_DIR' && .venv/bin/pip install --upgrade pip wheel setuptools"
sudo -u "$APP_USER" bash -lc "cd '$APP_DIR' && .venv/bin/pip install -r backend/requirements.txt"

sudo -u "$APP_USER" bash -lc "cd '$APP_DIR/frontend' && npm ci"
sudo -u "$APP_USER" bash -lc "cd '$APP_DIR/frontend' && npm run build"

install -d -o "$APP_USER" -g "$APP_GROUP" "$APP_DIR/backend/var/logs" "$APP_DIR/backend/var/backups"

for unit in tg-main.service tg-auth.service tg-ai.service tg-worker.service tg-web-auth.target tg-control-requests.service tg-control-requests.timer tg-daily-restart.service tg-daily-restart.timer; do
  sed \
    -e "s|/opt/tg-web-auth|$APP_DIR|g" \
    -e "s|User=tgapp|User=$APP_USER|g" \
    -e "s|Group=tgapp|Group=$APP_GROUP|g" \
    "$APP_DIR/deploy/linux/systemd/$unit" > "/etc/systemd/system/$unit"
done

systemctl daemon-reload
systemctl enable --now tg-auth.service tg-main.service tg-ai.service tg-worker.service
systemctl enable --now tg-control-requests.timer
systemctl enable --now tg-daily-restart.timer

sed \
  -e "s|example.com|$BASE_DOMAIN|g" \
  -e "s|server_name $BASE_DOMAIN;|server_name $FRONTEND_HOST;|g" \
  "$APP_DIR/deploy/linux/nginx/tg-web-auth.conf" > /etc/nginx/sites-available/tg-web-auth.conf

ln -sf /etc/nginx/sites-available/tg-web-auth.conf /etc/nginx/sites-enabled/tg-web-auth.conf
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl enable --now nginx
systemctl reload nginx

echo
echo "Deployment complete. Next steps:"
echo "1) Edit $APP_DIR/.env and set real TG/DeepSeek secrets"
echo "2) Update FRONTEND_ORIGINS to include https://$FRONTEND_HOST"
echo "3) Restart services: systemctl restart tg-auth tg-main tg-ai tg-worker"
echo "4) Configure TLS (recommended): certbot --nginx -d $FRONTEND_HOST -d api.$BASE_DOMAIN -d auth.$BASE_DOMAIN"
echo "5) Check status: systemctl status tg-auth tg-main tg-ai tg-worker tg-control-requests.timer tg-daily-restart.timer --no-pager"
