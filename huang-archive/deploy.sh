#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
HOST="${DEPLOY_HOST:-47.239.73.214}"
USER="${DEPLOY_USER:-root}"
PASS="${DEPLOY_PASS:-Hbs#2026}"
REMOTE_DIR="${REMOTE_DIR:-/opt/huang-archive}"

echo "==> Building frontend"
cd "$ROOT/frontend"
rm -rf node_modules
npm install
npm run build

echo "==> Ensuring sshpass"
if ! command -v sshpass >/dev/null 2>&1; then
  sudo apt-get update -qq && sudo apt-get install -y -qq sshpass
fi

SSH=(sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
SCP=(sshpass -p "$PASS" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
RSYNC_SSH="sshpass -p $PASS ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

echo "==> Preparing remote host"
"${SSH[@]}" "${USER}@${HOST}" "bash -s" <<'REMOTE'
set -e
export DEBIAN_FRONTEND=noninteractive
if ! command -v docker >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl
  curl -fsSL https://get.docker.com | sh
fi
mkdir -p /opt/huang-archive
REMOTE

echo "==> Syncing project"
if command -v rsync >/dev/null 2>&1; then
  rsync -az --delete \
    --exclude node_modules \
    --exclude .git \
    --exclude pocketbase/pb_data \
    -e "$RSYNC_SSH" \
    "$ROOT/" "${USER}@${HOST}:${REMOTE_DIR}/"
else
  "${SSH[@]}" "${USER}@${HOST}" "rm -rf ${REMOTE_DIR}.tmp && mkdir -p ${REMOTE_DIR}.tmp"
  tar czf - \
    --exclude=node_modules \
    --exclude=.git \
    --exclude=pocketbase/pb_data \
    -C "$ROOT" . | "${SSH[@]}" "${USER}@${HOST}" "tar xzf - -C ${REMOTE_DIR}.tmp && rm -rf ${REMOTE_DIR} && mv ${REMOTE_DIR}.tmp ${REMOTE_DIR}"
fi

echo "==> Building and starting containers"
"${SSH[@]}" "${USER}@${HOST}" "cd ${REMOTE_DIR} && docker compose down --remove-orphans || true && docker compose build --no-cache && docker compose up -d"

echo "==> Waiting for health"
for i in $(seq 1 36); do
  if curl -fsS "http://${HOST}/api/health" >/dev/null 2>&1; then
    echo "Health OK"
    break
  fi
  sleep 5
  if [ "$i" -eq 36 ]; then
    echo "Health check timed out" >&2
    "${SSH[@]}" "${USER}@${HOST}" "cd ${REMOTE_DIR} && docker compose logs --tail=80"
    exit 1
  fi
done

echo "Deploy complete: https://huangzhisong.com  /  http://${HOST}"
