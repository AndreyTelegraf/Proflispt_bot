#!/bin/bash

# Work in Portugal Bot Startup Script
echo "🚀 Starting Work in Portugal Bot..."

# Change to bot directory
cd /home/bot/workinportugal_bot

# Kill any existing processes
echo "🔄 Stopping existing processes..."
pkill -f "python3 main.py" 2>/dev/null || true
sleep 2

# Clear any stale lock files
echo "🧹 Cleaning up lock files..."
rm -f bot.lock bot_alt.lock 2>/dev/null || true

# Start the bot
echo "✅ Starting bot..."
python3 main.py
