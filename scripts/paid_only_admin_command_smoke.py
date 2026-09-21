#!/usr/bin/env python3
"""Smoke coverage for the /paid_only admin command."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from database import Database
import handlers.admin as admin_handler


class FakeMessage:
    def __init__(self, text: str, user_id: int):
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[str] = []

    async def answer(self, text: str, **_kwargs):
        self.answers.append(text)


def _create_user(database: Database, telegram_id: int, username: str) -> int:
    return database.create_user(telegram_id, username, "Test", None)


def _create_post(database: Database, user_id: int, payment_amount: float) -> int:
    return database.create_premium_post(
        user_id=user_id,
        mode="marketing",
        cities="Lisboa",
        description="Test post",
        social_media="",
        telegram_username="target_user",
        phone_main="+351910000001",
        phone_whatsapp="",
        name="Test",
        payment_amount=payment_amount,
    )


async def _run() -> None:
    with TemporaryDirectory() as tmp:
        database = Database(str(Path(tmp) / "paid-only-command.db"))
        original_db = admin_handler.db
        admin_handler.db = database
        try:
            target_id = _create_user(database, 1001, "target_user")
            free_post_id = _create_post(database, target_id, 0)
            before = database.get_premium_post(free_post_id)

            command = FakeMessage("/paid_only @target_user", admin_handler.ADMIN_IDS[0])
            await admin_handler.paid_only_user_command(command)
            assert database.is_paid_only_user(target_id)
            assert "только платные" in command.answers[-1]
            assert database.get_premium_post(free_post_id) == before

            repeated = FakeMessage("/paid_only @target_user", admin_handler.ADMIN_IDS[0])
            await admin_handler.paid_only_user_command(repeated)
            assert "уже доступны" in repeated.answers[-1]

            paid_post_id = _create_post(database, target_id, 20)
            assert paid_post_id > free_post_id
            try:
                _create_post(database, target_id, 0)
            except PermissionError:
                pass
            else:
                raise AssertionError("free post was accepted after /paid_only")

            numeric_id = _create_user(database, 1002, "numeric_target")
            numeric = FakeMessage("/paid_only 1002", admin_handler.ADMIN_IDS[0])
            await admin_handler.paid_only_user_command(numeric)
            assert database.is_paid_only_user(numeric_id)

            outsider_id = _create_user(database, 1003, "outsider_target")
            forbidden = FakeMessage("/paid_only @outsider_target", 999999)
            await admin_handler.paid_only_user_command(forbidden)
            assert not database.is_paid_only_user(outsider_id)
            assert "нет прав" in forbidden.answers[-1]

            missing = FakeMessage("/paid_only @missing", admin_handler.ADMIN_IDS[0])
            await admin_handler.paid_only_user_command(missing)
            assert "не найден" in missing.answers[-1]

            usage = FakeMessage("/paid_only", admin_handler.ADMIN_IDS[0])
            await admin_handler.paid_only_user_command(usage)
            assert "Использование" in usage.answers[-1]
        finally:
            admin_handler.db = original_db


def main() -> None:
    asyncio.run(_run())
    print("PAID_ONLY_ADMIN_COMMAND_SMOKE=OK")


if __name__ == "__main__":
    main()
