#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { printf "%s\n" "$*"; }
die() { printf "%s\n" "$*" >&2; exit 1; }

# ---------- env ----------
PYTHON_BIN="${PYTHON_BIN:-/usr/local/Caskroom/miniforge/base/envs/ismir_chord/bin/python}"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8710}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# 你的项目里已有这些变量：保留（可按需改默认值）
CHORD_REPO_DIR="${CHORD_REPO_DIR:-/Users/wujing/Documents/GitHub/web-chord_2/backend/ISMIR2019-Large-Vocabulary-Chord-Recognition}"
MAX_AUDIO_SECONDS="${MAX_AUDIO_SECONDS:-600}"
TRANSCODE_TO_WAV="${TRANSCODE_TO_WAV:-0}"

export CHORD_REPO_DIR MAX_AUDIO_SECONDS TRANSCODE_TO_WAV

log "[env] python: ${PYTHON_BIN}"
"${PYTHON_BIN}" -c 'import sys; print("[env] sys.executable:", sys.executable)' || true
log "[env] CHORD_REPO_DIR=${CHORD_REPO_DIR}"
log "[env] MAX_AUDIO_SECONDS=${MAX_AUDIO_SECONDS}"
log "[env] TRANSCODE_TO_WAV=${TRANSCODE_TO_WAV}"

# ---------- helpers ----------
open_url() {
  local url="$1"
  if command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
  else
    log "[info] open this url manually: $url"
  fi
}

cleanup() {
  log ""
  log "Stopping..."
  [[ -n "${FRONTEND_PID:-}" ]] && kill "${FRONTEND_PID}" >/dev/null 2>&1 || true
  [[ -n "${BACKEND_PID:-}" ]] && kill "${BACKEND_PID}" >/dev/null 2>&1 || true
}
trap cleanup INT TERM EXIT

# ---------- [1/4] backend deps (web api only) ----------
log "[1/4] backend deps (web api only) ..."
"${PYTHON_BIN}" -m pip -q install --upgrade pip >/dev/null 2>&1 || true
REQ_FILE="${ROOT_DIR}/backend/requirements.txt"
[[ -f "${REQ_FILE}" ]] || die "[error] requirements file not found: ${REQ_FILE}"
"${PYTHON_BIN}" -m pip install -r "${REQ_FILE}"

# 关键：把容易引发崩溃的 C 扩展卸掉（就算你机器里曾经装过也清掉）
"${PYTHON_BIN}" -m pip uninstall -y uvloop httptools >/dev/null 2>&1 || true

# ---------- [2/4] start backend (uvicorn) ----------
log "[2/4] start backend (uvicorn) ..."

export PYTHONFAULTHANDLER=1

BACKEND_LOG="${ROOT_DIR}/backend.log"
: > "${BACKEND_LOG}"

# 强制使用纯 python：--loop asyncio + --http h11
# 这样即使环境里还残留某些东西，也尽量不走 uvloop/httptools
"${PYTHON_BIN}" -X faulthandler -m uvicorn server:app \
  --app-dir "${ROOT_DIR}/backend" \
  --host "${BACKEND_HOST}" \
  --port "${BACKEND_PORT}" \
  --loop asyncio \
  --http h11 \
  --log-level info \
  > "${BACKEND_LOG}" 2>&1 &

BACKEND_PID=$!
log "[backend] pid=${BACKEND_PID} log=${BACKEND_LOG}"

# 等端口起来（不解析 JSON，避免你之前的 'Expecting value' 这种误导错误）
check_backend_up() {
  "${PYTHON_BIN}" - <<PY >/dev/null 2>&1
import sys, urllib.request
url = "http://${BACKEND_HOST}:${BACKEND_PORT}/health"
try:
    with urllib.request.urlopen(url, timeout=1.0) as r:
        # 只要能连上并返回任意内容就算 up
        _ = r.read(16)
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
}

ok=0
for _ in {1..30}; do
  if ! kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
    log "[error] backend crashed during startup (segfault or import crash). tail backend.log:"
    tail -n 120 "${BACKEND_LOG}" || true
    die "[error] backend is down"
  fi
  if check_backend_up; then
    ok=1
    break
  fi
  sleep 0.3
done

if [[ "${ok}" != "1" ]]; then
  log "[error] backend did not become healthy in time. tail backend.log:"
  tail -n 120 "${BACKEND_LOG}" || true
  die "[error] backend is not reachable"
fi

log "[check] backend health OK: http://${BACKEND_HOST}:${BACKEND_PORT}/health"

# ---------- [3/4] start frontend (static server) ----------
log "[3/4] start frontend (static server) ..."

PUBLIC_DIR="${ROOT_DIR}/public"
[[ -d "${PUBLIC_DIR}" ]] || die "[error] public/ not found: ${PUBLIC_DIR}"

# 用 http.server 确保不是 file:// 打开（file:// 会让 origin 变 null，触发你看到的 CORS）
"${PYTHON_BIN}" -m http.server "${FRONTEND_PORT}" --bind "${FRONTEND_HOST}" --directory "${PUBLIC_DIR}" \
  > "${ROOT_DIR}/frontend.log" 2>&1 &
FRONTEND_PID=$!

# ---------- [4/4] open ----------
FRONTEND_URL="http://${FRONTEND_HOST}:${FRONTEND_PORT}/index.html"
log "[4/4] open:"
log "  ${FRONTEND_URL}"
log ""
log "Press Ctrl+C to stop."
open_url "${FRONTEND_URL}"

# block
wait
