#!/bin/sh
set -e

mkdir -p /pb/pb_data /pb/pb_data/upload_sessions /pb/pb_data/transcode_tmp

# Apply migrations before admin bootstrap
/pb/pocketbase migrate up \
  --dir=/pb/pb_data \
  --migrationsDir=/pb/pb_migrations || true

if [ ! -f /pb/pb_data/.admin_bootstrapped ]; then
  /pb/pocketbase admin create \
    "${PB_ADMIN_EMAIL:-admin@huangzhisong.com}" \
    "${PB_ADMIN_PASSWORD:-HbsAdmin#2026}" \
    --dir=/pb/pb_data \
    || true
  touch /pb/pb_data/.admin_bootstrapped
fi

# Background transcoder for non-MP4 video → WeChat-friendly H.264 MP4
(
  sleep 8
  while true; do
    /pb/scripts/transcode_pending.sh || true
    sleep 12
  done
) &

exec /pb/pocketbase serve \
  --http=0.0.0.0:8090 \
  --dir=/pb/pb_data \
  --hooksDir=/pb/pb_hooks \
  --migrationsDir=/pb/pb_migrations
