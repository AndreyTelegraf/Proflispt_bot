#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot

from config import Config
from database import db
from services.directory_username_http_audit import send_directory_username_audit_report


async def main() -> None:
    limit = None
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])

    bot = Bot(token=Config.BOT_TOKEN)
    try:
        checked, issues = await send_directory_username_audit_report(bot, db, limit=limit)
        print(f"directory_username_http_audit_send OK checked={checked} issues={issues}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
