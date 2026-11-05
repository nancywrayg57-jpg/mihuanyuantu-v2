#!/usr/bin/env bash
# Run S0 PostgreSQL claim_one smoke on the registered development host.
# Password: env DEVHOST_SSH_PASS, or sibling ../生产物料/蜜獾原图v2-生产物料.md
set -euo pipefail

HOST="${DEVHOST_SSH_HOST:-192.168.19.128}"
USER="${DEVHOST_SSH_USER:-hbs}"
PORT="${DEVHOST_SSH_PORT:-22}"
REMOTE_REPO="${DEVHOST_REPO:-/home/hbs/hbs-projects/mihuanyuantu-v2}"
BRANCH="${DEVHOST_BRANCH:-cursor/s0-foundation-6c0b}"

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MATERIALS="$(cd "$REPO_ROOT/.." && pwd)/生产物料/蜜獾原图v2-生产物料.md"

if [[ -z "${DEVHOST_SSH_PASS:-}" && -f "$MATERIALS" ]]; then
  DEVHOST_SSH_PASS="$(sed -n 's/^| 密码 | `\([^`]*\)` |$/\1/p' "$MATERIALS" | head -1)"
fi
if [[ -z "${DEVHOST_SSH_PASS:-}" ]]; then
  echo "DEVHOST_SSH_PASS missing (export it or fill sibling 生产物料/)" >&2
  exit 2
fi
if ! command -v sshpass >/dev/null 2>&1; then
  echo "sshpass required for non-interactive SSH" >&2
  exit 2
fi

export SSHPASS="$DEVHOST_SSH_PASS"
SSH=(sshpass -e ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 -p "$PORT" "$USER@$HOST")

echo "==> probe $USER@$HOST:$PORT"
"${SSH[@]}" 'echo DEVHOST_OK; hostname; date -Is'

echo "==> checkout $BRANCH && run s0_pg_claim_one_smoke.py"
"${SSH[@]}" bash -s <<REMOTE
set -euo pipefail
cd "$REMOTE_REPO"
git fetch origin "$BRANCH" || true
git checkout "$BRANCH" 2>/dev/null || git checkout -B "$BRANCH" "origin/$BRANCH"
git pull --ff-only origin "$BRANCH" || true
cd aojuai-main/backend
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -U pip
  .venv/bin/pip install -e '.[dev]' || { .venv/bin/pip install -r requirements-dev.txt; .venv/bin/pip install -e .; }
fi
set -a
[[ -f .env ]] && . ./.env
set +a
export DB_DRIVER=postgresql
export AOJ_ENABLED_MODULES=realphotos
.venv/bin/python -m scripts.s0_pg_claim_one_smoke | tee /tmp/s0-pg-claim-one-smoke.log
REMOTE

echo "==> remote log: /tmp/s0-pg-claim-one-smoke.log"
