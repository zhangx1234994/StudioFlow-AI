#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-5005}"
HOST="${HOST:-0.0.0.0}"
SESSION_NAME="${SESSION_NAME:-aiphoto_${PORT}}"
LOG_FILE="${LOG_FILE:-${ROOT_DIR}/output/server.log}"
HEALTH_URL="http://127.0.0.1:${PORT}/api/v1/auth/me"

usage() {
  cat <<USAGE
Usage: scripts/dev_service.sh <up|down|restart|status|logs> [--skip-build]

Commands:
  up        Build frontend (default) and start backend in detached screen session
  down      Stop backend process and screen session
  restart   down + up
  status    Show running status
  logs      Tail backend log file

Options:
  --skip-build   Skip frontend build when running up/restart
USAGE
}

port_pid() {
  lsof -iTCP:"${PORT}" -sTCP:LISTEN -t 2>/dev/null || true
}

screen_session_exists() {
  screen -list 2>/dev/null | grep -q "\\.${SESSION_NAME}[[:space:]]"
}

wait_ready() {
  local attempts=0
  while [ "${attempts}" -lt 40 ]; do
    if curl -sSf "${HEALTH_URL}" >/dev/null 2>&1; then
      return 0
    fi
    attempts=$((attempts + 1))
    sleep 0.5
  done
  return 1
}

ensure_dirs() {
  mkdir -p "${ROOT_DIR}/output"
}

build_frontend() {
  echo "[service] building frontend..."
  npm --prefix "${ROOT_DIR}/frontend" run build
}

start_server() {
  ensure_dirs
  local existing
  existing="$(port_pid)"
  if [ -n "${existing}" ]; then
    echo "[service] already running on port ${PORT} (pid=${existing})"
    return 0
  fi
  if ! command -v screen >/dev/null 2>&1; then
    echo "[service] screen not found. install screen first."
    exit 1
  fi
  if screen_session_exists; then
    screen -S "${SESSION_NAME}" -X quit || true
    sleep 0.5
  fi
  echo "[service] starting backend in screen session ${SESSION_NAME}..."
  screen -dmS "${SESSION_NAME}" bash -lc "cd \"${ROOT_DIR}\" && exec python3 -m uvicorn app.main:app --host ${HOST} --port ${PORT} >> \"${LOG_FILE}\" 2>&1"
  if wait_ready; then
    local pid
    pid="$(port_pid)"
    echo "[service] started. pid=${pid:-unknown}, port=${PORT}"
  else
    echo "[service] failed to become ready. recent logs:"
    tail -n 80 "${LOG_FILE}" || true
    exit 1
  fi
}

stop_server() {
  local pids
  pids="$(port_pid)"
  if [ -n "${pids}" ]; then
    echo "[service] stopping pid(s): ${pids}"
    kill ${pids} || true
    sleep 1
  fi
  pids="$(port_pid)"
  if [ -n "${pids}" ]; then
    echo "[service] force stopping pid(s): ${pids}"
    kill -9 ${pids} || true
  fi
  if command -v screen >/dev/null 2>&1 && screen_session_exists; then
    echo "[service] closing screen session ${SESSION_NAME}"
    screen -S "${SESSION_NAME}" -X quit || true
  fi
  echo "[service] stopped"
}

status_server() {
  local pid
  pid="$(port_pid)"
  if [ -n "${pid}" ]; then
    echo "[service] running pid=${pid} port=${PORT}"
  else
    echo "[service] not running"
  fi
  if command -v screen >/dev/null 2>&1 && screen_session_exists; then
    echo "[service] screen session=${SESSION_NAME} active"
  fi
}

logs_server() {
  ensure_dirs
  tail -n 120 -f "${LOG_FILE}"
}

main() {
  if [ "$#" -lt 1 ]; then
    usage
    exit 1
  fi
  local cmd="$1"
  shift || true
  local skip_build="false"
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --skip-build)
        skip_build="true"
        ;;
      *)
        echo "unknown option: $1"
        usage
        exit 1
        ;;
    esac
    shift || true
  done

  case "${cmd}" in
    up)
      if [ "${skip_build}" != "true" ]; then
        build_frontend
      fi
      start_server
      ;;
    down)
      stop_server
      ;;
    restart)
      stop_server
      if [ "${skip_build}" != "true" ]; then
        build_frontend
      fi
      start_server
      ;;
    status)
      status_server
      ;;
    logs)
      logs_server
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
