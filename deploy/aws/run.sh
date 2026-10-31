#!/bin/bash
# Build and (re)start FasalNetra on one server: app container + Caddy (automatic HTTPS).
# Usage, from the repo root on the server:  ./deploy/aws/run.sh 13-205-168-88.sslip.io
# Secrets go in .env.server next to this repo (TWILIO_*, DEMO_FARMER_PHONE, VISION_PROVIDER, SMS_LINK_SIGNING_SECRET);
# PUBLIC_BASE_URL and the data paths are set here.
set -euo pipefail
HOST="${1:?public hostname, e.g. 13-205-168-88.sslip.io}"
cd "$(dirname "$0")/../.."

docker build -t fasalnetra .
docker network inspect web >/dev/null 2>&1 || docker network create web
touch .env.server

docker rm -f app >/dev/null 2>&1 || true
docker run -d --name app --network web --restart unless-stopped \
  --env-file .env.server \
  -e PUBLIC_BASE_URL="https://$HOST" \
  -e DATABASE_URL=sqlite+aiosqlite:////var/lib/fasalnetra/fasalnetra.db \
  -e UPLOAD_DIR=/var/lib/fasalnetra/uploads \
  -v fasalnetra-data:/var/lib/fasalnetra \
  fasalnetra

printf '%s {\n\treverse_proxy app:7860\n}\n' "$HOST" > Caddyfile
docker rm -f caddy >/dev/null 2>&1 || true
docker run -d --name caddy --network web --restart unless-stopped \
  -p 80:80 -p 443:443 \
  -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" -v caddy-data:/data \
  caddy:2.8

echo "FasalNetra: https://$HOST  (Twilio voice webhook: https://$HOST/api/v1/ivr/webhook)"
