#!/bin/bash
set -euo pipefail

# QEMU server deployment script
# Config is read from .env (QEMU_SERVER, QEMU_SSH_KEY)
# Usage: ./deploy_qemu.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load .env
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

: "${QEMU_SERVER:?Set QEMU_SERVER in .env (e.g. root@1.2.3.4)}"
: "${QEMU_SSH_KEY:?Set QEMU_SSH_KEY in .env (e.g. ~/.ssh/id_exe)}"

echo "==> Syncing code to $QEMU_SERVER..."
rsync -avz --delete --exclude='.git' --exclude='.env' \
  -e "ssh -i $QEMU_SSH_KEY" \
  "$SCRIPT_DIR/" "$QEMU_SERVER":~/cloudpebble/

echo "==> Building and restarting qemu service..."
ssh -i "$QEMU_SSH_KEY" "$QEMU_SERVER" "cd ~/cloudpebble && docker compose --profile emulator build qemu && docker compose --profile emulator up -d qemu"

echo "==> Done. Checking container status..."
ssh -i "$QEMU_SSH_KEY" "$QEMU_SERVER" "cd ~/cloudpebble && docker compose --profile emulator ps qemu"
