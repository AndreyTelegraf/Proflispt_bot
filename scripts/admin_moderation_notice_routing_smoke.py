from __future__ import annotations

import asyncio
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.admin_moderation_notice import send_admin_moderation_notice


class FakeBot:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return object()


async def main() -> None:
    bot = FakeBot()
    await send_admin_moderation_notice(
        bot,
        admin_chat_id=8405113240,
        post_id=123,
        preview_text="Preview",
        control_text="Controls",
        media_list=[],
    )

    assert len(bot.calls) == 2, bot.calls
    assert all(call["chat_id"] == 8405113240 for call in bot.calls), bot.calls
    assert bot.calls[0]["text"] == "Preview"
    assert bot.calls[1]["text"] == "Controls"


asyncio.run(main())
print("admin_moderation_notice_routing_smoke OK")
