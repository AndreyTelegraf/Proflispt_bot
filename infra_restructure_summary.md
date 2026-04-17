# Droplet & Bots Restructure — Final State

## 1. Droplet Upgrade

- RAM увеличена с ~512MB до 1GB
- Swap: 2GB
- После апсайза:
  - свободная RAM стабилизировалась
  - swap pressure существенно снизился
  - Cursor extension host перестал падать по OOM

---

## 2. Архитектура ботов (финальное состояние)

### Docker-based боты

Работают через docker-compose:

- langtest_bot
- onlyads_bot
- workinportugal_bot (docker-версия)

### Systemd-based бот

Отдельно работает polling-версия:

- workinportugal_bot.service

**Путь:** /opt/bots/workinportugal_bot

**Запуск:** /opt/bots/workinportugal_bot/venv/bin/python main.py

---

## 3. Удалённые / отключённые компоненты

### ba_raholka_bot

- systemd unit остановлен
- отключён
- замаскирован
- контейнер не используется

Проект признан неактуальным.

---

## 4. Исправление путаницы workin(g)portugal

**Было:**

- workingportugal_bot
- workinportugal_bot
- workingportugal-bot.service
- workinportugal-bot.service

**Что сделано:**

- Убит неправильный бот
- Восстановлен нужный бот
- Каталог приведён к единому имени: /opt/bots/workinportugal_bot
- Старые systemd-юниты замаскированы (-> /dev/null)
- Создан корректный юнит: workinportugal_bot.service

**Финальный статус:**

- Loaded: loaded
- Enabled: yes
- Active: running

---

## 5. Docker Resource Limits

### onlyads_bot (самый лёгкий)

mem_limit: 140m
memswap_limit: 140m
cpus: "0.15"
cpu_shares: 128

Фактическое потребление: ~38MB

### langtest_bot (самый тяжёлый)

~100MB RAM — основная нагрузка.

### workinportugal_bot (docker)

~96MB RAM

---

## 6. Логи Docker

Глобально настроено:

"log-driver": "json-file"
"log-opts": { "max-size": "10m", "max-file": "3" }

Ротация работает. Логи не раздувают диск.

---

## 7. Cursor Stability

**Причина таймаутов:**

- RAM 458MB
- активный swap
- extensionHost падал
- sandbox user namespace error (ожидаемо на DO)

**После апсайза до 1GB:**

- Cursor стабилен
- extensionHost не умирает
- Agent Execution Timed Out исчез

---

## 8. Финальная структура

/opt/bots/
    workinportugal_bot/

/srv/
    langtest/
    onlyads/
    workinportugal/

/etc/systemd/system/
    workinportugal_bot.service
    (старые working* -> masked)

/mnt/volume_ams3_01/docker/
    containers/
    logs (rotated)

---

## 9. Текущее распределение нагрузки

- Самый нагруженный: langtest_bot
- Средний: workinportugal_bot
- Самый лёгкий: onlyads_bot

---

## 10. Система сейчас

- RAM: 1GB
- Swap: 2GB
- Все healthchecks healthy
- Docker стабилен
- systemd чистый
- Старых процессов нет
- Конфликтующих юнитов нет
- Дубликатов workin(g)portugal нет
