#!/usr/bin/env python3
"""Script to update and restart the bot with conflict resolution."""

import subprocess
import time
import logging
import sys
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_command(command, description):
    """Run a command and log the result."""
    logger.info(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"✅ {description} - успешно")
            return True
        else:
            logger.error(f"❌ {description} - ошибка: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"❌ {description} - исключение: {e}")
        return False

def update_and_restart():
    """Update and restart the bot with conflict resolution."""
    
    logger.info("🚀 Начинаем процесс обновления и перезапуска бота...")
    
    # 1. Остановить бота
    if not run_command("pkill -f 'python3 main.py'", "Останавливаем бота"):
        logger.warning("⚠️ Не удалось остановить бота, продолжаем...")
    
    time.sleep(2)
    
    # 2. Исправить конфликт Telegram
    logger.info("🔧 Исправляем конфликт Telegram...")
    if not run_command("python3 fix_telegram_conflict.py", "Исправление конфликта"):
        logger.error("❌ Не удалось исправить конфликт Telegram")
        return False
    
    # 3. Проверить статус Git (если есть изменения)
    if os.path.exists(".git"):
        logger.info("📝 Проверяем Git статус...")
        run_command("git status", "Проверка Git статуса")
    
    # 4. Запустить бота
    logger.info("🚀 Запускаем бота...")
    try:
        subprocess.Popen(["python3", "main.py"], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE)
        logger.info("✅ Бот запущен в фоновом режиме")
    except Exception as e:
        logger.error(f"❌ Не удалось запустить бота: {e}")
        return False
    
    # 5. Проверить статус
    time.sleep(3)
    logger.info("🔍 Проверяем статус бота...")
    run_command("tail -5 bot.log", "Проверка логов")
    
    logger.info("🎉 Обновление и перезапуск завершены!")
    return True

def quick_restart():
    """Quick restart without full update process."""
    
    logger.info("⚡ Быстрый перезапуск бота...")
    
    # 1. Остановить бота
    run_command("pkill -f 'python3 main.py'", "Останавливаем бота")
    time.sleep(3)  # Увеличиваем время ожидания
    
    # 2. Исправить конфликт
    run_command("python3 fix_telegram_conflict.py", "Исправление конфликта")
    
    # 3. Дополнительная проверка конфликта
    logger.info("🔍 Дополнительная проверка конфликта...")
    time.sleep(2)
    run_command("python3 fix_telegram_conflict.py", "Повторная проверка")
    
    # 4. Запустить бота
    try:
        subprocess.Popen(["python3", "main.py"], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE)
        logger.info("✅ Бот запущен в фоновом режиме")
    except Exception as e:
        logger.error(f"❌ Не удалось запустить бота: {e}")
    
    # 5. Проверить статус
    time.sleep(5)  # Увеличиваем время ожидания
    run_command("tail -5 bot.log", "Проверка логов")
    
    logger.info("✅ Быстрый перезапуск завершен!")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        quick_restart()
    else:
        update_and_restart()
