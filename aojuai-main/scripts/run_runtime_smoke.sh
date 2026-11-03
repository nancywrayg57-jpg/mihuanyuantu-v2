#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)

BACKEND_URL=${BACKEND_URL:-http://127.0.0.1:8000}
TEST_USERNAME=${TEST_USERNAME:-admin}
TEST_PASSWORD=${TEST_PASSWORD:-Admin@123456}

cd "$ROOT_DIR/backend"
uv run python scripts/smoke_test_runtime_core.py \
  --base-url "$BACKEND_URL" \
  --username "$TEST_USERNAME" \
  --password "$TEST_PASSWORD" \
  "$@"
