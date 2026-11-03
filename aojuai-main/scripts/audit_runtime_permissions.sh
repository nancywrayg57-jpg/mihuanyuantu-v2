#!/usr/bin/env bash
# 运行时权限审计（部署门禁）：运行目录所有权、日志所有权、同一 checkout 重复进程、模型/业务要读的静态资产可读性。
# 回流自 nextjs-plugins 3c9c4543，改为清单驱动：base 只带内核项，业务分支在 scripts/audit_runtime_permissions.local
# 里追加（同名数组 += 即可），不在本文件里出现业务路径。
set -euo pipefail

MODE="${1:---check}"
if [[ "$MODE" != "--check" && "$MODE" != "--fix" ]]; then
  echo "usage: $0 [--check|--fix]" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="${AOJU_RUNTIME_USER:-www}"
RUN_GROUP="${AOJU_RUNTIME_GROUP:-www}"
BT_LOG_ROOT="${AOJU_BT_LOG_ROOT:-/www/wwwlogs/python}"
failed=0

# 内核清单（业务分支勿改，追加到 .local）
runtime_dirs=(
  "$REPO_ROOT/backend/run"
  "$REPO_ROOT/backend/logs"
  "$REPO_ROOT/run"
)
# worker 以 $RUN_USER 运行；root 在 umask 077 会话里 git pull 会得到 600 文件 → 进程读不到代码/提示词/模板。
# 必须世界可读；--fix 时 chmod a+rX。
readable_dirs=(
  "$REPO_ROOT/backend/app"
  "$REPO_ROOT/backend/alembic"
  "$REPO_ROOT/backend/scripts"
)
runtime_logs=(
  "$BT_LOG_ROOT/backend/error.log"
)
# "label|pgrep 正则"：同一 checkout（按 /proc/<pid>/cwd 判）下每种进程只允许一个
process_checks=(
  "backend web|^[^ ]*/python[^ ]* [^ ]*/uvicorn app\.main:app "
  "frontend Next.js|^next-server "
)

LOCAL_LIST="$REPO_ROOT/scripts/audit_runtime_permissions.local"
if [[ -f "$LOCAL_LIST" ]]; then
  # shellcheck disable=SC1090
  source "$LOCAL_LIST"
fi

if [[ "$MODE" == "--fix" && "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "--fix must run as root" >&2
  exit 2
fi

for path in "${runtime_dirs[@]}"; do
  if [[ "$MODE" == "--fix" ]]; then
    install -d -m 0755 -o "$RUN_USER" -g "$RUN_GROUP" "$path"
    chown -R "$RUN_USER:$RUN_GROUP" "$path"
  fi
  if [[ ! -d "$path" ]]; then
    echo "missing runtime directory: $path" >&2
    failed=1
    continue
  fi
  if find "$path" -xdev \( ! -user "$RUN_USER" -o ! -group "$RUN_GROUP" \) -print -quit | grep -q .; then
    echo "runtime ownership mismatch: $path" >&2
    failed=1
  fi
  if ! runuser -u "$RUN_USER" -- test -w "$path"; then
    echo "runtime directory is not writable by $RUN_USER: $path" >&2
    failed=1
  fi
done

for path in "${runtime_logs[@]}"; do
  [[ -e "$path" ]] || continue
  if [[ "$MODE" == "--fix" ]]; then
    chown "$RUN_USER:$RUN_GROUP" "$path"
  fi
  owner="$(stat -c '%U:%G' "$path")"
  if [[ "$owner" != "$RUN_USER:$RUN_GROUP" ]]; then
    echo "runtime log ownership mismatch: $owner $path" >&2
    failed=1
  fi
done

check_duplicate_processes() {
  local label="$1"
  local pattern="$2"
  local count=0
  local pid cwd
  local -a matched_pids=()
  mapfile -t matched_pids < <(pgrep -f "$pattern" 2>/dev/null || true)
  for pid in "${matched_pids[@]}"; do
    cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
    if [[ "$cwd" == "$REPO_ROOT" || "$cwd" == "$REPO_ROOT/"* ]]; then
      count=$((count + 1))
    fi
  done
  if (( count > 1 )); then
    echo "duplicate $label processes for this checkout: $count" >&2
    failed=1
  fi
}

for entry in "${process_checks[@]}"; do
  check_duplicate_processes "${entry%%|*}" "${entry#*|}"
done

for path in "${readable_dirs[@]}"; do
  [[ -e "$path" ]] || continue
  if find "$path" -xdev \( -type f ! -perm -o=r -o -type d ! -perm -o=x \) -print -quit | grep -q .; then
    if [[ "$MODE" == "--fix" ]]; then
      chmod -R a+rX "$path"
      echo "fixed readability: $path"
    else
      echo "NOT world-readable (process as $RUN_USER cannot read it): $path" >&2
      failed=1
    fi
  fi
done

if (( failed != 0 )); then
  exit 1
fi
echo "runtime permission audit passed"
