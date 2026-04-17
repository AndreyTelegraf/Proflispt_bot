#!/usr/bin/env python3
"""Universal bot utilities script."""

import requests
import json
import subprocess
import time
import logging
import sys
import os
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_bot_info():
    """Check bot information."""
    bot_token = Config.BOT_TOKEN
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    
    print("🔍 Checking bot information...")
    
    try:
        response = requests.get(url)
        result = response.json()
        
        if result.get('ok'):
            bot_info = result.get('result', {})
            print("✅ Bot info retrieved successfully:")
            print(f"   ID: {bot_info.get('id')}")
            print(f"   Name: {bot_info.get('first_name')}")
            print(f"   Username: @{bot_info.get('username')}")
            return True
        else:
            print("❌ Failed to get bot info")
            print(f"   Error: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Error getting bot info: {e}")
        return False

def check_webhook_status():
    """Check webhook status."""
    bot_token = Config.BOT_TOKEN
    url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
    
    print("\n🔍 Checking webhook status...")
    
    try:
        response = requests.get(url)
        result = response.json()
        
        if result.get('ok'):
            webhook_info = result.get('result', {})
            print("✅ Webhook info retrieved:")
            print(f"   URL: {webhook_info.get('url', 'Not set')}")
            print(f"   Has custom certificate: {webhook_info.get('has_custom_certificate', False)}")
            print(f"   Pending updates: {webhook_info.get('pending_update_count', 0)}")
            print(f"   Allowed updates: {webhook_info.get('allowed_updates', [])}")
            return webhook_info
        else:
            print("❌ Failed to get webhook info")
            print(f"   Error: {result}")
            return None
            
    except Exception as e:
        print(f"❌ Error getting webhook info: {e}")
        return None

def check_updates():
    """Check for pending updates."""
    bot_token = Config.BOT_TOKEN
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    
    print("\n🔍 Checking for pending updates...")
    
    try:
        response = requests.get(url)
        result = response.json()
        
        if result.get('ok'):
            updates = result.get('result', [])
            print(f"✅ Found {len(updates)} pending updates")
            
            if updates:
                print("   Recent updates:")
                for i, update in enumerate(updates[-3:]):  # Show last 3
                    update_id = update.get('update_id')
                    print(f"     Update {i+1}: ID={update_id}")
            return updates
        else:
            print("❌ Failed to get updates")
            print(f"   Error: {result}")
            return None
            
    except Exception as e:
        print(f"❌ Error getting updates: {e}")
        return None

def reset_updates():
    """Reset all updates for the bot."""
    bot_token = Config.BOT_TOKEN
    
    print("🔄 Resetting bot updates...")
    
    try:
        # Delete webhook
        delete_webhook_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
        response = requests.get(delete_webhook_url)
        result = response.json()
        print(f"Delete webhook result: {result}")
        
        # Get updates with offset to clear queue
        get_updates_url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        params = {"offset": -1, "limit": 1}
        
        response = requests.get(get_updates_url, params=params)
        result = response.json()
        
        if result.get('ok') and result.get('result'):
            # Get the last update_id and set offset to clear all updates
            last_update = result['result'][-1]
            last_update_id = last_update['update_id']
            
            # Set offset to clear all updates
            clear_params = {"offset": last_update_id + 1}
            response = requests.get(get_updates_url, params=clear_params)
            clear_result = response.json()
            print(f"Clear updates result: {clear_result}")
            
        print("✅ Bot updates reset completed!")
        
    except Exception as e:
        print(f"❌ Error resetting bot updates: {e}")

def force_restart():
    """Force restart with conflict resolution."""
    
    logger.info("🔥 Принудительный перезапуск бота...")
    
    # 1. Остановить все процессы
    logger.info("1️⃣ Останавливаем все процессы...")
    subprocess.run(["pkill", "-f", "python3 main.py"], check=False)
    subprocess.run(["pkill", "-9", "-f", "python3 main.py"], check=False)
    time.sleep(5)
    
    # 2. Удалить webhook и очистить обновления
    logger.info("2️⃣ Очищаем состояние бота...")
    reset_updates()
    time.sleep(2)
    
    # 3. Запустить бота
    logger.info("3️⃣ Запускаем бота...")
    try:
        process = subprocess.Popen(
            ["python3", "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info(f"✅ Бот запущен (PID: {process.pid})")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        return False
    
    # 4. Проверить статус
    time.sleep(5)
    logger.info("4️⃣ Проверяем статус...")
    try:
        result = subprocess.run(["tail", "-5", "bot.log"], 
                              capture_output=True, text=True, timeout=10)
        if result.stdout:
            logger.info("📋 Последние логи:")
            for line in result.stdout.strip().split('\n'):
                logger.info(f"   {line}")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось прочитать логи: {e}")
    
    logger.info("🎉 Принудительный перезапуск завершен!")
    return True

def diagnose():
    """Complete bot diagnosis."""
    print("🔍 Complete Bot Diagnosis")
    print("=" * 50)
    
    # Check bot info
    if not check_bot_info():
        print("❌ Cannot proceed - bot connection failed")
        return False
    
    # Check webhook status
    check_webhook_status()
    
    # Check updates
    updates = check_updates()
    
    # Check running processes
    print("\n🔍 Checking running processes...")
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        bot_processes = [line for line in result.stdout.split('\n') if 'main.py' in line and 'grep' not in line]
        
        if bot_processes:
            print("✅ Found running bot processes:")
            for process in bot_processes:
                print(f"   {process}")
        else:
            print("❌ No running bot processes found")
    except Exception as e:
        print(f"❌ Error checking processes: {e}")
    
    # Check log files
    print("\n🔍 Checking log files...")
    log_files = ["bot.log", "bot_output.log"]
    for log_file in log_files:
        if os.path.exists(log_file):
            size = os.path.getsize(log_file)
            print(f"   {log_file}: {size} bytes")
        else:
            print(f"   {log_file}: Not found")
    
    return True

def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python3 bot_utils.py <command>")
        print("Commands:")
        print("  diagnose    - Complete bot diagnosis")
        print("  restart     - Force restart bot")
        print("  reset       - Reset bot updates")
        print("  info        - Show bot info")
        print("  webhook     - Show webhook status")
        print("  updates     - Show pending updates")
        return
    
    command = sys.argv[1].lower()
    
    if command == "diagnose":
        diagnose()
    elif command == "restart":
        force_restart()
    elif command == "reset":
        reset_updates()
    elif command == "info":
        check_bot_info()
    elif command == "webhook":
        check_webhook_status()
    elif command == "updates":
        check_updates()
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main()
