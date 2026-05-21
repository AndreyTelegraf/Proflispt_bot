#!/bin/bash

# Proflistpt Bot Restart Script
echo "Restarting Proflistpt Bot..."

# Use the utility script for restart
python3 bot_utils.py restart

echo ""
echo "✅ Bot restart completed!"
echo "📋 Check logs: tail -f bot.log"
