#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/aojuai-main/backend"
set -a; source .env; set +a
OVERRIDE="$(.venv/bin/python - <<'PY'
import os, urllib.parse
print(f"postgresql+asyncpg://{os.environ['DB_USER']}:{urllib.parse.quote_plus(os.environ['DB_PASSWORD'])}@/{os.environ['DB_NAME']}?host=/tmp")
PY
)"
# Worktrees resolve UPLOAD_DIR relative to cwd → empty static/realphotos, while DB
# object_key rows still point at the main-tree LocalDisk. Pin a shared absolute root.
if [[ -z "${REALPHOTOS_STORAGE_ROOT:-}" ]]; then
  COMMON="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
  if [[ -n "$COMMON" ]]; then
    MAIN_ROOT="$(cd "$(dirname "$COMMON")" && pwd)"
    CANDIDATE="$MAIN_ROOT/aojuai-main/backend/static/realphotos"
    if [[ -d "$CANDIDATE" ]]; then
      export REALPHOTOS_STORAGE_ROOT="$CANDIDATE"
    fi
  fi
fi
LOCAL_STORAGE="$ROOT/aojuai-main/backend/static/realphotos"
if [[ -n "${REALPHOTOS_STORAGE_ROOT:-}" && "$REALPHOTOS_STORAGE_ROOT" != "$LOCAL_STORAGE" ]]; then
  mkdir -p "$(dirname "$LOCAL_STORAGE")"
  if [[ -L "$LOCAL_STORAGE" || ! -e "$LOCAL_STORAGE" ]] || [[ -d "$LOCAL_STORAGE" && -z "$(ls -A "$LOCAL_STORAGE" 2>/dev/null || true)" ]]; then
    rm -rf "$LOCAL_STORAGE"
    ln -sfn "$REALPHOTOS_STORAGE_ROOT" "$LOCAL_STORAGE"
  fi
fi
echo "REALPHOTOS_STORAGE_ROOT=${REALPHOTOS_STORAGE_ROOT:-<(default relative)>}"
pkill -f 'uvicorn app.main:app --host 127.0.0.1 --port 38000' 2>/dev/null || true
pkill -f 'scripts.run_worker --worker realphotos_heartbeat' 2>/dev/null || true
pkill -f 'next dev -H 127.0.0.1 -p 3000' 2>/dev/null || true
sleep 2
export DATABASE_URL_OVERRIDE="$OVERRIDE" REALPHOTOS_IMPORT_STAGING=true
nohup .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 38000 > /tmp/local-preview-api.log 2>&1 &
echo api_pid=$!
nohup .venv/bin/python -m scripts.run_worker --worker realphotos_heartbeat --concurrency 1 > /tmp/local-preview-worker.log 2>&1 &
echo worker_pid=$!
cd "$ROOT/aojuai-main/frontend"
nohup ./node_modules/.bin/next dev -H 127.0.0.1 -p 3000 > /tmp/local-preview-next.log 2>&1 &
echo fe_pid=$!
sleep 8
curl -sS -o /dev/null -w 'api:%{http_code}\n' http://127.0.0.1:38000/api/v1/openapi.json || true
curl -sS -o /dev/null -w 'fe:%{http_code}\n' http://127.0.0.1:3000/ || true
