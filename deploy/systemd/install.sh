#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

APP_DIR="${1:-/opt/studioflow-ai}"
SERVICE_NAME="studioflow-ai.service"
SRC_SERVICE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/${SERVICE_NAME}"
DST_SERVICE="/etc/systemd/system/${SERVICE_NAME}"

if [ ! -d "${APP_DIR}" ]; then
  echo "App directory does not exist: ${APP_DIR}"
  exit 1
fi

cp "${SRC_SERVICE}" "${DST_SERVICE}"
sed -i "s#/opt/studioflow-ai#${APP_DIR}#g" "${DST_SERVICE}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"
systemctl --no-pager --full status "${SERVICE_NAME}"
