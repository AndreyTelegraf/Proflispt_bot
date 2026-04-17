# Work in Portugal Bot

Telegram бот для публикации объявлений о работе в Португалии.

## Установка

1. Клонируйте репозиторий
2. Установите зависимости: `pip3 install -r requirements.txt`
3. Настройте `config.py` с вашим токеном бота
4. Запустите: `python3 main.py`

## Обновление и перезапуск бота

### Быстрый перезапуск (рекомендуется)

```bash
# Самый простой способ
./restart.sh

# Или принудительный перезапуск
python3 force_restart.py
```

### Дополнительные опции

```bash
# Быстрый перезапуск
python3 update_and_restart.py --quick

# Полное обновление с проверкой конфликтов
python3 update_and_restart.py
```

### Разрешение конфликтов Telegram

Если бот выдает ошибку `TelegramConflictError`, выполните:

```bash
python3 fix_telegram_conflict.py
```

Этот скрипт автоматически:
1. Остановит все процессы бота
2. Удалит webhook
3. Очистит обновления с offset
4. Проверит статус

## Ручное разрешение конфликтов

Если автоматический скрипт не помог:

```bash
# 1. Остановить бота
pkill -f "python3 main.py"

# 2. Удалить webhook
curl -s "https://api.telegram.org/botYOUR_TOKEN/deleteWebhook"

# 3. Очистить обновления
curl -s "https://api.telegram.org/botYOUR_TOKEN/getUpdates?offset=999999999"

# 4. Запустить бота
python3 main.py
```

## Функции

- ✅ Публикация объявлений "Ищу работу"
- ✅ Публикация объявлений "Предлагаю работу"
- ✅ Поддержка множественных городов
- ✅ Социальные сети (Instagram, X, LinkedIn, Facebook, Threads и др.)
- ✅ Автоматическое форматирование
- ✅ Предварительный просмотр
- ✅ Управление объявлениями

## Структура проекта

```
├── main.py                 # Главный файл бота
├── config.py              # Конфигурация
├── database.py            # Работа с базой данных
├── utils.py               # Утилиты
├── fix_telegram_conflict.py # Скрипт разрешения конфликтов
├── handlers/              # Обработчики команд
├── services/              # Сервисы
├── models/                # Модели данных
└── requirements.txt       # Зависимости
```
