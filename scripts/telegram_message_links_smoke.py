from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault("DIRECTORY_CHANNEL_USERNAME", "@proflistpt")

from services.directory_links import directory_message_url, telegram_message_url
from services.premium_admin_dispatcher import build_message_link


assert telegram_message_url("@proflistpt", 38404, 8490) == (
    "https://t.me/proflistpt/8490/38404"
)
assert telegram_message_url("proflistpt", 38404) == (
    "https://t.me/proflistpt/38404"
)
assert directory_message_url(38404, 8490) == (
    "https://t.me/proflistpt/8490/38404"
)


class FakeBot:
    async def get_chat(self, chat_id: int):
        usernames = {
            -1001788799608: "proflistpt",
            -1001620950645: "baraholka_pt",
        }
        return SimpleNamespace(username=usernames[chat_id])


async def run() -> None:
    bot = FakeBot()

    directory_link = await build_message_link(
        bot,
        chat_id=-1001788799608,
        message_id=38404,
        topic_id=8490,
    )
    assert directory_link == "https://t.me/proflistpt/8490/38404"

    baraholka_link = await build_message_link(
        bot,
        chat_id=-1001620950645,
        message_id=443962,
        topic_id=53479,
    )
    assert baraholka_link == "https://t.me/baraholka_pt/53479/443962"

    plain_link = await build_message_link(
        bot,
        chat_id=-1001788799608,
        message_id=38404,
    )
    assert plain_link == "https://t.me/proflistpt/38404"


asyncio.run(run())
print("TELEGRAM_MESSAGE_LINKS_SMOKE=OK")
