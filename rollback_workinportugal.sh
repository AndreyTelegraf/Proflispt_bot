#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: ./rollback_workinportugal.sh /tmp/workinportugal_predeploy_<TS>.tar.gz"
  exit 1
fi

REMOTE_HOST="do-prod"
REMOTE_DIR="/opt/bots/workinportugal_bot"
SERVICE="workinportugal_bot.service"
BACKUP_ARCHIVE="$1"

ssh "$REMOTE_HOST" "
set -euo pipefail
REMOTE_DIR='$REMOTE_DIR'
SERVICE='$SERVICE'
BACKUP_ARCHIVE='$BACKUP_ARCHIVE'

test -f \"$BACKUP_ARCHIVE\"

sudo tar -xzf \"$BACKUP_ARCHIVE\" -C \"$REMOTE_DIR\"
sudo chown -R root:root \"$REMOTE_DIR\"
sudo systemctl restart \"$SERVICE\"
sleep 3
sudo systemctl is-active \"$SERVICE\"
sudo systemctl status \"$SERVICE\" --no-pager -n 40
sudo journalctl -u \"$SERVICE\" -n 80 --no-pager
"
