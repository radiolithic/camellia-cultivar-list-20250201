#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/deploy.conf"

echo "Restarting ${SERVICE_NAME}..."
systemctl restart "${SERVICE_NAME}"
echo "Done. Current status:"
systemctl status "${SERVICE_NAME}" --no-pager
