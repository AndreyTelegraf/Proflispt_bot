from __future__ import annotations

import asyncio
import io
import sys
import time
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.directory_username_http_audit import (
    DirectoryUsernameAuditIssue,
    audit_directory_usernames,
    build_directory_username_audit_report,
    check_public_tme_post,
    check_public_tme_username,
    normalize_telegram_username,
    send_directory_username_audit_report,
    username_slug,
    verify_directory_username_audit_candidates,
)

assert normalize_telegram_username("@Kak_odin") == "@Kak_odin"
assert normalize_telegram_username("https://t.me/Kak_odin") == "@Kak_odin"
assert normalize_telegram_username("telegram.me/Kak_odin/") == "@Kak_odin"
assert normalize_telegram_username("") == ""
assert username_slug("@Kak_odin") == "Kak_odin"


class FakeResponse:
    def __init__(self, body: str, status: int = 200):
        self.status = status
        self._body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, limit: int) -> bytes:
        return self._body[:limit]


valid_response = FakeResponse('<div class="tgme_page_wrap"><div class="tgme_page_title">Valid</div></div>')
with patch(
    "services.directory_username_http_audit.urllib.request.urlopen",
    side_effect=[urllib.error.URLError(TimeoutError("temporary")), valid_response],
) as mocked_urlopen:
    assert check_public_tme_username("@valid_after_retry", retry_delay=0) == (True, None)
    assert mocked_urlopen.call_count == 2

with patch(
    "services.directory_username_http_audit.urllib.request.urlopen",
    side_effect=urllib.error.URLError(TimeoutError("temporary")),
) as mocked_urlopen:
    ok, reason = check_public_tme_username("@temporarily_unavailable", retry_delay=0)
    assert ok is None
    assert reason and "inconclusive after 3 attempts" in reason
    assert mocked_urlopen.call_count == 3

with patch(
    "services.directory_username_http_audit.urllib.request.urlopen",
    side_effect=RuntimeError("unexpected transport failure"),
) as mocked_urlopen:
    ok, reason = check_public_tme_username("@unexpected_failure", retry_delay=0)
    assert ok is None
    assert reason and "RuntimeError" in reason and "inconclusive after 3 attempts" in reason
    assert mocked_urlopen.call_count == 3

not_found = urllib.error.HTTPError("https://t.me/missing", 404, "Not Found", {}, io.BytesIO())
with patch(
    "services.directory_username_http_audit.urllib.request.urlopen",
    side_effect=not_found,
) as mocked_urlopen:
    ok, reason = check_public_tme_username("@missing", retry_delay=0)
    assert ok is False
    assert reason and "t.me returned 404" in reason and "confirmed by 3 attempts" in reason
    assert mocked_urlopen.call_count == 3

missing_page = FakeResponse(
    '<div class="tgme_page_description">\n'
    '  If you have <strong>Telegram</strong>, you can contact '
    '<a href="tg://resolve?domain=missing">@missing</a> right away.\n'
    '</div>'
)
with patch(
    "services.directory_username_http_audit.urllib.request.urlopen",
    return_value=missing_page,
) as mocked_urlopen:
    ok, reason = check_public_tme_username("@missing", retry_delay=0)
    assert ok is None
    assert reason and "ambiguous generic contact page" in reason
    assert mocked_urlopen.call_count == 3

with patch(
    "services.directory_username_http_audit.urllib.request.urlopen",
    side_effect=[missing_page, valid_response],
) as mocked_urlopen:
    assert check_public_tme_username("@recovers_from_false_not_found", retry_delay=0) == (True, None)
    assert mocked_urlopen.call_count == 2

live_post_page = FakeResponse(
    '<meta property="og:title" content="Proflistpt_bot in Directory">'
    '<meta property="og:description" content="Listing text @working">'
)
with patch(
    "services.directory_username_http_audit.urllib.request.urlopen",
    return_value=live_post_page,
) as mocked_urlopen:
    assert check_public_tme_post(
        "https://t.me/proflistpt/1/101",
        expected_username="@working",
        retry_delay=0,
    ) == (True, None)
    assert mocked_urlopen.call_count == 1

missing_post_page = FakeResponse(
    '<meta property="og:title" content="Directory">'
    '<meta property="og:description" content="Directory landing page">'
    '<div class="tgme_page_title">Directory</div>'
)
with patch(
    "services.directory_username_http_audit.urllib.request.urlopen",
    return_value=missing_post_page,
) as mocked_urlopen:
    ok, reason = check_public_tme_post(
        "https://t.me/proflistpt/1/102",
        expected_username="@missing",
        retry_delay=0,
    )
    assert ok is False
    assert reason and "channel landing page" in reason and "confirmed by 3 attempts" in reason
    assert mocked_urlopen.call_count == 3

rows = [
    {
        "id": 1,
        "mode": "realtors",
        "description": "One",
        "telegram_username": "@SameUser",
        "message_id": 101,
        "topic_id": 1,
        "published_message_ids": None,
    },
    {
        "id": 2,
        "mode": "realtors",
        "description": "Two",
        "telegram_username": "@sameuser",
        "message_id": 102,
        "topic_id": 1,
        "published_message_ids": None,
    },
    {
        "id": 3,
        "mode": "realtors",
        "description": "Three",
        "telegram_username": "@temporary",
        "message_id": 103,
        "topic_id": 1,
        "published_message_ids": None,
    },
]


def fake_check(username: str, **kwargs):
    if username.casefold() == "@sameuser":
        return False, "t.me returned 404"
    return None, "t.me timeout after 3 attempts"


with patch("services.directory_username_http_audit.load_published_directory_contact_rows", return_value=rows), patch(
    "services.directory_username_http_audit.check_public_tme_username",
    side_effect=fake_check,
) as mocked_check:
    checked, confirmed, unavailable = audit_directory_usernames(
        object(),
        max_workers=2,
        confirmation_workers=1,
        confirmation_cooldown=0,
    )
    assert checked == 3
    assert [issue.post_id for issue in confirmed] == [1, 2]
    assert [issue.post_id for issue in unavailable] == [3]
    assert mocked_check.call_count == 4

report = build_directory_username_audit_report(
    checked_count=2,
    issues=[
        DirectoryUsernameAuditIssue(
            post_id=123,
            username="@missing_user",
            reason="t.me returned 404",
            section_name="Грузовые перевозки",
            display_title="Тестовое объявление",
            post_url="https://t.me/proflistpt/1/2",
        )
    ],
    unavailable=[
        DirectoryUsernameAuditIssue(
            post_id=124,
            username="@temporary_user",
            reason="t.me timeout after 3 attempts",
            section_name="Риелторы",
            display_title="Временно недоступен",
            post_url="https://t.me/proflistpt/1/3",
        )
    ],
    stale_publications=[
        DirectoryUsernameAuditIssue(
            post_id=125,
            username="@stale_user",
            reason="Telegram publication is absent",
            section_name="Риелторы",
            display_title="Удалённая публикация",
            post_url="https://t.me/proflistpt/1/4",
        )
    ],
)

assert "Записей со статусом «опубликовано» в базе: 2" in report
assert "Подтверждённо неработающих контактов в доступных объявлениях: 1" in report
assert "Временно не удалось проверить: 1" in report
assert "Пропущено отсутствующих публикаций: 1" in report
assert "База автоматически не изменялась" in report
assert "@missing_user" in report
assert "@temporary_user" in report
assert "Грузовые перевозки #123" in report


class VerificationBot:
    async def get_chat(self, target):
        usernames = {
            -1001: "proflistpt",
            10: "working",
            20: "old_missing_post",
            30: "new_username",
        }
        if target in usernames:
            return SimpleNamespace(username=usernames[target])
        raise RuntimeError("not resolvable by Bot API")


def candidate(post_id, username, owner_id, owner_username):
    return DirectoryUsernameAuditIssue(
        post_id=post_id,
        username=username,
        reason="ambiguous t.me page",
        section_name="Риелторы",
        display_title=f"Post {post_id}",
        post_url=None,
        chat_id=-1001,
        message_id=post_id,
        topic_id=1,
        owner_telegram_id=owner_id,
        owner_username=owner_username,
    )


async def assert_verified_candidates() -> None:
    candidates = [
        candidate(101, "@working", 10, "@working"),
        candidate(102, "@old_missing_post", 20, "@old_missing_post"),
        candidate(103, "@old_username", 30, "@old_username"),
    ]

    def fake_post_check(url, **kwargs):
        if url.endswith("/102"):
            return False, "publication missing confirmed"
        return True, None

    with patch(
        "services.directory_username_http_audit.check_public_tme_post",
        side_effect=fake_post_check,
    ):
        confirmed, unavailable, stale = await verify_directory_username_audit_candidates(
            VerificationBot(),
            [],
            candidates,
        )

    assert [item.post_id for item in confirmed] == [103]
    assert "changed from @old_username to @new_username" in confirmed[0].reason
    assert unavailable == []
    assert [item.post_id for item in stale] == [102]
    assert stale[0].post_url == "https://t.me/proflistpt/1/102"


asyncio.run(assert_verified_candidates())


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)


async def assert_send_does_not_block_event_loop() -> None:
    def slow_audit(db, *, limit=None):
        time.sleep(0.15)
        return 2, [], []

    bot = FakeBot()
    with patch("services.directory_username_http_audit.audit_directory_usernames", side_effect=slow_audit):
        task = asyncio.create_task(
            send_directory_username_audit_report(bot, object(), fallback_admin_chat_id=1)
        )
        await asyncio.sleep(0.02)
        assert not task.done(), "audit blocked the event loop"
        assert await task == (2, 0, 0, 0)
    assert bot.messages


asyncio.run(assert_send_does_not_block_event_loop())

print("directory_username_http_audit_smoke OK")
