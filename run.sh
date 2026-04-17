#!/usr/bin/env bash
set -euo pipefail
cd /home/bot/workinportugal_bot
exec /home/bot/.venv/bin/python /home/bot/workinportugal_bot/main.py
# или если это пакет:
# exec /home/bot/.venv/bin/python -m workinportugal_bot.main
