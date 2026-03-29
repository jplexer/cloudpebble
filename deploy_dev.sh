#!/bin/bash
set -euo pipefail

# Deploy to dev (cloudpebble-dev.exe.xyz)
# All services on one box: web, celery, postgres, redis, s3, qemu, nginx
# Uses local postgres — NOT Supabase
#
# Usage: ./deploy_dev.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_HOST="cloudpebble-dev.exe.xyz"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_exe}"
SSH="ssh -i $SSH_KEY $DEV_HOST"

echo "==> Syncing code to $DEV_HOST..."
rsync -avz --delete \
  --exclude='.git' \
  --exclude='.env' \
  --exclude='.env.local' \
  --exclude='.DS_Store' \
  -e "ssh -i $SSH_KEY" \
  "$SCRIPT_DIR/" "$DEV_HOST":~/cloudpebble/

echo "==> Building images..."
$SSH "cd ~/cloudpebble && docker compose --profile emulator --profile codecomplete build"

echo "==> Restarting services..."
$SSH "cd ~/cloudpebble && docker compose --profile emulator --profile codecomplete down && docker compose --profile emulator --profile codecomplete up -d"

echo "==> Waiting for web to start..."
sleep 5

echo "==> Container status:"
$SSH "cd ~/cloudpebble && docker compose --profile emulator --profile codecomplete ps"

echo ""
echo "==> Web logs (last 15 lines):"
$SSH "cd ~/cloudpebble && docker compose logs web --tail 15"

echo ""
echo "==> Deploy complete: https://$DEV_HOST/"
