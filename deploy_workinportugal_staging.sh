#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="do-prod"
REMOTE_DIR="/opt/bots/workinportugal_bot_staging"
SERVICE="workinportugal_bot_staging.service"
TS=$(date -u +%Y%m%dT%H%M%SZ)
TMP_ARCHIVE="/tmp/workinportugal_staging_code_$TS.tar.gz"

python3 -m py_compile main.py config.py database.py handlers/*.py services/*.py middleware/*.py keyboards/*.py models/*.py

COPYFILE_DISABLE=1 tar \
  --exclude=".git" \
  --exclude=".venv" \
  --exclude="__pycache__" \
  --exclude="*.pyc" \
  --exclude=".env" \
  --exclude="*.db" \
  --exclude="*.sqlite" \
  --exclude="*.sqlite3" \
  --exclude="bot.log" \
  --exclude="bot_output.log" \
  --exclude="logs/*.log" \
  --exclude="*.tar.gz" \
  -czf "$TMP_ARCHIVE" .

scp "$TMP_ARCHIVE" "$REMOTE_HOST:/tmp/workinportugal_staging_code_$TS.tar.gz"

ssh "$REMOTE_HOST" "
set -euo pipefail
REMOTE_DIR='$REMOTE_DIR'
SERVICE='$SERVICE'
TS='$TS'
ARCHIVE='/tmp/workinportugal_staging_code_$TS.tar.gz'

sudo test -d \"\$REMOTE_DIR\"
sudo test -f \"\$REMOTE_DIR/.env\"
sudo test -f \"\$REMOTE_DIR/bot_database.db\"

sudo tar -czf \"/tmp/workinportugal_staging_predeploy_\$TS.tar.gz\" -C \"\$REMOTE_DIR\" .
sudo tar -xzf \"\$ARCHIVE\" -C \"\$REMOTE_DIR\"
sudo chown -R root:root \"\$REMOTE_DIR\"

sudo systemctl restart \"\$SERVICE\"
sleep 3
sudo systemctl is-active \"\$SERVICE\"
sudo systemctl status \"\$SERVICE\" --no-pager -n 40
sudo journalctl -u \"\$SERVICE\" -n 80 --no-pager
echo
echo \"STAGING_BACKUP=/tmp/workinportugal_staging_predeploy_\$TS.tar.gz\"
"
