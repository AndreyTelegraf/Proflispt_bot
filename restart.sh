#!/bin/bash

# Work in Portugal Bot Restart Script
echo "🔄 Restarting Work in Portugal Bot..."

# Use the utility script for restart
python3 bot_utils.py restart

echo ""
echo "✅ Bot restart completed!"
echo "📋 Check logs: tail -f bot.log"
