#!/usr/bin/env bash
# Run ON 开发机 (hbs@192.168.19.128) after submitting one gpsMode=none task.
# Writes /tmp/r6-devhost-task.json for fix_failure_rate_remain_e2e.py R6 gate.
# Usage (example): TASK_ID=123 ./scripts/r6_devhost_evidence_stub.sh
set -euo pipefail
TASK_ID="${TASK_ID:?set TASK_ID}"
GPS_MODE="${GPS_MODE:-none}"
STATUS="${STATUS:?set STATUS e.g. DELIVERED or FAILED}"
FAILURE_CLASS="${FAILURE_CLASS:-}"
FAILURE_MESSAGE="${FAILURE_MESSAGE:-}"
python3 - <<PY
import json
payload={
  "taskId": int("${TASK_ID}"),
  "gpsMode": "${GPS_MODE}",
  "status": "${STATUS}",
  "failureClass": "${FAILURE_CLASS}",
  "failureMessage": """${FAILURE_MESSAGE}""",
}
open("/tmp/r6-devhost-task.json","w",encoding="utf-8").write(json.dumps(payload,ensure_ascii=False,indent=2))
print("wrote /tmp/r6-devhost-task.json", payload)
PY
