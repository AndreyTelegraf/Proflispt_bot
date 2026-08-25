from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import Database
from services.admin_moderation_notice import _approval_keyboard
from services.baraholka_repost_request import create_and_notify_baraholka_repost_request
from services.my_postings_repost import handle_my_postings_repost_request
from services.my_postings_view import premium_post_action_rows, premium_post_status_label
from services.premium_repost_policy import (
    BUMP_KIND,
    REPUBLISH_KIND,
    premium_repost_policy,
    validate_premium_repost_request,
)
from services.premium_repost_request import build_repost_admin_notes
from services.premium_request_labels import premium_request_label


published = {"status": "published", "mode": "teaching", "action_type": "post"}
expired = {
    "status": "deleted",
    "mode": "teaching",
    "action_type": "post",
    "expired_notified_at": "2026-08-25 00:00:00",
}
self_deleted = {"status": "deleted", "mode": "teaching", "action_type": "post"}
admin_blocked = {
    "status": "published",
    "mode": "teaching",
    "action_type": "post",
    "repost_blocked_at": "2026-08-25 12:00:00",
}

assert premium_repost_policy(published).kind == BUMP_KIND
assert premium_repost_policy(expired).kind == REPUBLISH_KIND
assert not premium_repost_policy(self_deleted).allowed
assert premium_repost_policy(self_deleted).reason == "user_deleted"
assert not premium_repost_policy(admin_blocked).allowed
assert premium_repost_policy(admin_blocked).reason == "admin_blocked"

assert premium_post_action_rows(published, 1)[0][0].text == "Поднять — €10"
assert premium_post_action_rows(expired, 2)[0][0].text == "Опубликовать снова — €10"
assert premium_post_action_rows(self_deleted, 3) == []
blocked_rows = premium_post_action_rows(admin_blocked, 4)
assert blocked_rows == []
assert premium_post_status_label(admin_blocked) == "Заблокировано администратором"

assert premium_request_label(
    action_type="repost",
    mode="teaching",
    payment_amount=10,
    repost_kind=BUMP_KIND,
) == "Ап объявления — €10"
assert premium_request_label(
    action_type="repost",
    mode="teaching",
    payment_amount=10,
    repost_kind=REPUBLISH_KIND,
) == "Повторная публикация — €10"

notes = json.loads(build_repost_admin_notes({"id": 9}, repost_kind=REPUBLISH_KIND))
assert notes["repost_kind"] == REPUBLISH_KIND
assert notes["old_post_id"] == 9

keyboard = _approval_keyboard(10, allow_source_block=True)
assert keyboard.inline_keyboard[1][0].callback_data == "admin:block_repost_source:10"


class FakeCallback:
    def __init__(self):
        self.answers = []

    async def answer(self, text, *, show_alert):
        self.answers.append((text, show_alert))


async def assert_stale_callback_is_denied() -> None:
    callback = FakeCallback()
    await handle_my_postings_repost_request(
        callback,
        db=object(),
        post=self_deleted,
        user={"id": 1},
        admin_chat_id=1,
    )
    assert callback.answers == [
        ("Вы удалили это объявление. Для новой публикации создайте новую заявку.", True)
    ]


asyncio.run(assert_stale_callback_is_denied())

with tempfile.TemporaryDirectory() as tmp:
    temp_db = Database(str(Path(tmp) / "policy.db"))
    with temp_db.get_connection() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(premium_posts)")}
    assert {"repost_blocked_at", "repost_blocked_reason", "repost_blocked_by"} <= columns

    user_id = temp_db.create_user(telegram_id=1001, username="policy_user")
    source_id = temp_db.create_premium_post(
        user_id=user_id,
        mode="teaching",
        cities="[]",
        description="Source",
        telegram_username="@policy_user",
        phone_main="+351000000000",
        name="Policy User",
        media_list=[],
        payment_amount=0,
        action_type="post",
    )
    with temp_db.get_connection() as conn:
        conn.execute(
            "UPDATE premium_posts SET status='published', payment_status='approved' WHERE id=?",
            (source_id,),
        )
        conn.commit()

    source = temp_db.get_premium_post(source_id)
    request_id = temp_db.create_premium_post(
        user_id=user_id,
        mode="teaching",
        cities="[]",
        description="Source",
        telegram_username="@policy_user",
        phone_main="+351000000000",
        name="Policy User",
        media_list=[],
        payment_amount=10,
        action_type="repost",
        admin_notes=build_repost_admin_notes(source, repost_kind=BUMP_KIND),
    )
    blocked_source_id = temp_db.block_repost_source_from_request(
        request_id,
        admin_id=777,
        reason="smoke block",
    )
    assert blocked_source_id == source_id
    assert temp_db.get_premium_post(source_id)["repost_blocked_reason"] == "smoke block"
    request = temp_db.get_premium_post(request_id)
    assert request["payment_status"] == "rejected"
    assert json.loads(request["admin_notes"])["moderation_result"] == "rejected_source_blocked"

    stale_request_id = temp_db.create_premium_post(
        user_id=user_id,
        mode="teaching",
        cities="[]",
        description="Source",
        telegram_username="@policy_user",
        phone_main="+351000000000",
        name="Policy User",
        media_list=[],
        payment_amount=10,
        action_type="repost",
        admin_notes=build_repost_admin_notes(source, repost_kind=BUMP_KIND),
    )
    stale_request = temp_db.get_premium_post(stale_request_id)
    try:
        validate_premium_repost_request(temp_db, stale_request)
    except ValueError as exc:
        assert "запрещена администратором" in str(exc)
    else:
        raise AssertionError("Admin-blocked source must fail approval validation")

    async def assert_blocked_baraholka_callback_is_denied() -> None:
        try:
            await create_and_notify_baraholka_repost_request(
                object(),
                db=temp_db,
                source_post_id=source_id,
                user={"id": user_id},
                admin_chat_id=1,
            )
        except ValueError as exc:
            assert "запрещена администратором" in str(exc)
        else:
            raise AssertionError("Admin-blocked source must not create a Baraholka request")

    asyncio.run(assert_blocked_baraholka_callback_is_denied())

print("my_postings_repost_policy_smoke OK")
