#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

RENPY_SDK_PATH="${RENPY_SDK_PATH:-/home/hosung/pytorch-demo/renpy-8.3.0-sdk}"
BACKEND_HOST="${DATE_SAYA_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${DATE_SAYA_BACKEND_PORT:-8010}"
BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
BACKEND_LOG="${SCRIPT_DIR}/backend.log"
BACKEND_PID=""

cleanup() {
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ ! -x "${RENPY_SDK_PATH}/renpy.sh" ]]; then
  echo "[ERROR] renpy.sh not found: ${RENPY_SDK_PATH}/renpy.sh"
  exit 1
fi

echo "[INFO] Starting backend at ${BACKEND_URL} ..."
(
  cd "${ROOT_DIR}"
  uv run uvicorn date_saya_backend.api:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}"
) >"${BACKEND_LOG}" 2>&1 &
BACKEND_PID=$!

echo "[INFO] Waiting for backend health check ..."
for _ in $(seq 1 180); do
  if python3 - "${BACKEND_URL}" <<'PY'
import json
import sys
import urllib.request

url = sys.argv[1].rstrip("/") + "/health"
try:
    with urllib.request.urlopen(url, timeout=1.5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    ok = isinstance(data, dict) and data.get("status") == "ok"
except Exception:
    ok = False
print("ok" if ok else "not_ok")
sys.exit(0 if ok else 1)
PY
  then
    break
  fi
  sleep 1
done

if ! python3 - "${BACKEND_URL}" <<'PY'
import json
import sys
import urllib.request

url = sys.argv[1].rstrip("/") + "/health"
with urllib.request.urlopen(url, timeout=2.0) as resp:
    data = json.loads(resp.read().decode("utf-8"))
assert data.get("status") == "ok"
PY
then
  echo "[ERROR] Backend failed to become healthy."
  echo "        Check log: ${BACKEND_LOG}"
  exit 1
fi

echo "[INFO] Backend ready. Launching Ren'Py ..."
echo "[INFO] Backend log: ${BACKEND_LOG}"
"${RENPY_SDK_PATH}/renpy.sh" "${SCRIPT_DIR}"

