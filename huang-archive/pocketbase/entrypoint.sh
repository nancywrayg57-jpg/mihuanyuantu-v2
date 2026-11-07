#!/bin/sh
set -e

mkdir -p /pb/pb_data

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

exec /pb/pocketbase serve \
  --http=0.0.0.0:8090 \
  --dir=/pb/pb_data \
  --hooksDir=/pb/pb_hooks \
  --migrationsDir=/pb/pb_migrations
