#!/usr/bin/env bash
# A-gate: reject committed secret files / high-risk patterns in tracked files.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

fail=0

echo "== Forbidden path basename check =="
while IFS= read -r -d '' path; do
  base="$(basename "$path")"
  case "$base" in
    .env|.env.local|.env.production|id_rsa|id_ed25519)
      echo "FAIL: tracked secret-like path: $path"
      fail=1
      ;;
    *.pem)
      echo "FAIL: tracked PEM: $path"
      fail=1
      ;;
  esac
done < <(git ls-files -z)

echo "== High-risk content patterns (tracked text files) =="
# Skip obvious binary/vendor paths; scan source/docs/config only.
mapfile -t files < <(git ls-files \
  | grep -E '\.(py|ts|tsx|js|mjs|cjs|json|ya?ml|toml|md|sh|env|ini|cfg|txt)$' \
  | grep -Ev '(^|/)(pnpm-lock\.yaml|package-lock\.json)$' \
  || true)

patterns=(
  'BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY'
  'AKIA[0-9A-Z]{16}'
  'ghp_[A-Za-z0-9]{20,}'
  'github_pat_[A-Za-z0-9_]{20,}'
  'xox[baprs]-[A-Za-z0-9-]{10,}'
)

for f in "${files[@]:-}"; do
  [[ -f "$f" ]] || continue
  # Allow documented placeholders only
  if grep -nE "${patterns[0]}|${patterns[1]}|${patterns[2]}|${patterns[3]}|${patterns[4]}" "$f" 2>/dev/null \
    | grep -Ev '(YOUR_|CHANGE_ME|REDACTED|example\.com|placeholder|sk-xxxx|\*\*\*)' >/tmp/secret_scan_hits.txt; then
    if [[ -s /tmp/secret_scan_hits.txt ]]; then
      echo "FAIL: suspicious secret material in $f"
      cat /tmp/secret_scan_hits.txt
      fail=1
    fi
  fi
done

if [[ "$fail" -ne 0 ]]; then
  echo "::error::Secret red-line scan failed"
  exit 1
fi

echo "Secret red-line scan passed"
