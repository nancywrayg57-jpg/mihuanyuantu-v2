#!/usr/bin/env bash
# 轻量档（SQLite）一条命令运维：init / run / upgrade / backup / doctor
# 用法：scripts/lite.sh <init|run|upgrade|backup|doctor> [--port 8000]
set -euo pipefail

SELF="$(readlink -f "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SELF")/.." && pwd)"
BACKEND="$REPO_ROOT/backend"
PY="${AOJU_PYTHON:-$BACKEND/.venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"
CMD="${1:-}"; shift || true
PORT=8000
while [[ $# -gt 0 ]]; do case "$1" in --port) PORT="$2"; shift 2;; *) echo "unknown arg: $1" >&2; exit 2;; esac; done

cd "$BACKEND"
if [[ ! -f .env ]]; then
  cp .env.lite.template .env
  echo "已从 .env.lite.template 生成 backend/.env（请修改 SECRET_KEY / PROVIDER_SECRET_KEY）"
fi
export DB_DRIVER="${DB_DRIVER:-sqlite}"
DB_PATH="$(grep -E '^SQLITE_PATH=' .env | tail -1 | cut -d= -f2- || true)"; DB_PATH="${SQLITE_PATH:-${DB_PATH:-./data/aoju.db}}"
mkdir -p "$(dirname "$DB_PATH")"

case "$CMD" in
  init)
    # 核心链 + 各能力包迁移链 + 菜单/权限/角色对账；空库走 create_all + stamp（双方言迁移只在存量库重放）
    "$PY" -m scripts.capability db upgrade
    "$PY" -m scripts.capability sync
    "$PY" -m scripts.seed_data
    echo "init 完成：$DB_PATH"
    ;;
  run)
    exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
    ;;
  upgrade)
    "$SELF" backup
    "$PY" -m scripts.capability db upgrade
    "$PY" -m scripts.capability sync
    echo "upgrade 完成；后端进程没有 --reload 的话请重启"
    ;;
  backup)
    mkdir -p "$(dirname "$DB_PATH")/backups"
    OUT="$(dirname "$DB_PATH")/backups/$(basename "$DB_PATH" .db)-$(date +%Y%m%d-%H%M%S).db"
    # 用 sqlite3 在线备份 API：WAL 下直接 cp 文件会丢未 checkpoint 的写入
    "$PY" - "$DB_PATH" "$OUT" <<'PYEOF'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
    s.backup(d)
print(f"backup: {dst}")
PYEOF
    ;;
  doctor)
    "$PY" - "$DB_PATH" <<'PYEOF'
import os, sqlite3, sys
from app.core.config import settings
from app.core.dialect_features import unavailable_features
db = sys.argv[1]
print("profile        :", settings.DEPLOY_PROFILE, "| dialect:", "sqlite" if settings.IS_SQLITE else "postgresql")
print("redis          :", "enabled" if settings.REDIS_ENABLED_EFFECTIVE else "disabled (local cache)")
print("begin mode     :", settings.SQLITE_BEGIN_MODE)
print("db file        :", db, "| exists:", os.path.exists(db), "| size:", os.path.getsize(db) if os.path.exists(db) else 0)
if os.path.exists(db):
    c = sqlite3.connect(db)
    print("journal_mode   :", c.execute("pragma journal_mode").fetchone()[0], "| integrity:", c.execute("pragma integrity_check").fetchone()[0])
    print("core head      :", [r[0] for r in c.execute("select version_num from alembic_version")] if c.execute("select count(*) from sqlite_master where name='alembic_version'").fetchone()[0] else "(未初始化)")
    packs = [r[0] for r in c.execute("select name from sqlite_master where name like 'alembic_version_cap_%'")]
    for t in packs:
        print("pack head      :", t.replace("alembic_version_cap_", ""), [r[0] for r in c.execute(f"select version_num from {t}")])
    print("tables         :", c.execute("select count(*) from sqlite_master where type='table'").fetchone()[0])
print("unavailable    :", unavailable_features() or "(none)")
PYEOF
    ;;
  *)
    echo "usage: $0 <init|run|upgrade|backup|doctor> [--port N]" >&2; exit 2;;
esac
