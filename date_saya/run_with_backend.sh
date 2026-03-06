#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# Override via env if needed.
RENPY_SDK_PATH="${RENPY_SDK_PATH:-/home/hosung/pytorch-demo/renpy-8.3.0-sdk}"
BACKEND_HOST="${DATE_SAYA_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${DATE_SAYA_BACKEND_PORT:-8010}"
BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
LLM_HOST="${DATE_SAYA_LLM_HOST:-127.0.0.1}"
LLM_PORT="${DATE_SAYA_LLM_PORT:-8100}"
LLM_URL="http://${LLM_HOST}:${LLM_PORT}"
START_LLM="${DATE_SAYA_START_LLM:-0}"
LLM_MODEL_PATH="${DATE_SAYA_LLM_MODEL_PATH:-${ROOT_DIR}/date_saya_backend/model_assets/saya_rp_4b_v3}"
LLM_SERVED_MODEL_NAME="${DATE_SAYA_LLM_SERVED_MODEL_NAME:-saya-rp-4b}"
LLM_MAX_MODEL_LEN="${DATE_SAYA_LLM_MAX_MODEL_LEN:-1536}"
LLM_GPU_UTIL="${DATE_SAYA_LLM_GPU_UTIL:-0.40}"
LLM_MAX_NUM_SEQS="${DATE_SAYA_LLM_MAX_NUM_SEQS:-1}"

BACKEND_LOG="${SCRIPT_DIR}/backend.log"
LLM_LOG="${SCRIPT_DIR}/llm.log"
BACKEND_PID=""
LLM_PID=""

cleanup() {
  if [[ -n "${LLM_PID}" ]] && kill -0 "${LLM_PID}" 2>/dev/null; then
    kill "${LLM_PID}" 2>/dev/null || true
    wait "${LLM_PID}" 2>/dev/null || true
  fi
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ ! -x "${RENPY_SDK_PATH}/renpy.sh" ]]; then
  echo "[ERROR] renpy.sh not found: ${RENPY_SDK_PATH}/renpy.sh"
  echo "        Set RENPY_SDK_PATH to your Ren'Py SDK path."
  exit 1
fi

if [[ "${START_LLM}" == "1" ]]; then
  if ! python3 - "${LLM_URL}" <<'PY'
import json
import sys
import urllib.request
url = sys.argv[1].rstrip("/") + "/v1/models"
try:
    with urllib.request.urlopen(url, timeout=1.2) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    ok = isinstance(data, dict)
except Exception:
    ok = False
sys.exit(0 if ok else 1)
PY
  then
    echo "[INFO] Starting local LLM server at ${LLM_URL} ..."
    (
      cd "${ROOT_DIR}"
      /home/hosung/pytorch-demo/RomanceArena/.venv/bin/python -m vllm.entrypoints.openai.api_server \
        --host "${LLM_HOST}" \
        --port "${LLM_PORT}" \
        --model "${LLM_MODEL_PATH}" \
        --served-model-name "${LLM_SERVED_MODEL_NAME}" \
        --max-model-len "${LLM_MAX_MODEL_LEN}" \
        --gpu-memory-utilization "${LLM_GPU_UTIL}" \
        --max-num-seqs "${LLM_MAX_NUM_SEQS}" \
        --enable-auto-tool-choice \
        --tool-call-parser qwen3_xml \
        --enforce-eager
    ) >"${LLM_LOG}" 2>&1 &
    LLM_PID=$!
  else
    echo "[INFO] Detected existing LLM server at ${LLM_URL}"
  fi
fi

if [[ "${START_LLM}" == "1" ]]; then
  echo "[INFO] Waiting for LLM readiness ..."
  LLM_OK=0
  for _ in $(seq 1 60); do
    if python3 - "${LLM_URL}" <<'PY'
import json
import sys
import urllib.request
url = sys.argv[1].rstrip("/") + "/v1/models"
try:
    with urllib.request.urlopen(url, timeout=1.5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    ok = isinstance(data, dict) and ("data" in data)
except Exception:
    ok = False
sys.exit(0 if ok else 1)
PY
    then
      LLM_OK=1
      break
    fi
    sleep 1
  done
  if [[ "${LLM_OK}" != "1" ]]; then
    echo "[ERROR] LLM server did not become ready."
    echo "        Check log: ${LLM_LOG}"
    echo "        Tip: close other GPU apps or lower DATE_SAYA_LLM_GPU_UTIL (e.g. 0.30)."
    exit 1
  fi
fi

echo "[INFO] Starting backend at ${BACKEND_URL} ..."
(
  cd "${ROOT_DIR}"
  export DATE_SAYA_LLM_BASE_URL="${LLM_URL}/v1"
  export DATE_SAYA_LLM_MODEL="${LLM_SERVED_MODEL_NAME}"
  export LLM_BACKEND="${LLM_BACKEND:-hf}"
  export LLM_STRICT_VLLM="${LLM_STRICT_VLLM:-0}"
  uv run uvicorn date_saya_backend.api:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}"
) >"${BACKEND_LOG}" 2>&1 &
BACKEND_PID=$!

echo "[INFO] Waiting for backend health check ..."
for _ in $(seq 1 60); do
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
if [[ "${START_LLM}" == "1" ]]; then
  echo "[INFO] LLM log: ${LLM_LOG}"
fi
"${RENPY_SDK_PATH}/renpy.sh" "${SCRIPT_DIR}"
