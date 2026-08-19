"""Read-only smoke checks for the moderated Talk to Me publication flow."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from config import Config
from database import Database, db
import handlers.generic_schema_flow as generic_flow
from handlers.generic_schema_flow import _preview_kb, _step_kb
from handlers.section_catalog import _sections_keyboard
from services.catalog_listing_renderer import render_talk_to_me_listing_html
from services.catalog_modes import (
    MODE_TO_SECTION_NAME,
    TALK_TO_ME_MODE,
    TALK_TO_ME_SECTION_NAME,
)
from services.moderated_free_sections import (
    build_talk_to_me_listing_payload,
    validate_talk_to_me_payload,
)
from services.my_postings_view import premium_post_action_rows, premium_post_status_label
from services.premium_admin_notifications import (
    build_approval_user_notification,
    build_rejection_user_notification,
)
from services.premium_publish_plan import build_premium_publish_plan
from services.premium_publisher import publish_premium_post_to_telegram
from services.premium_request_labels import premium_request_label
from services.schema_bootstrap import build_schema_registry
from services.schema_flow_adapter import SchemaFlowAdapter
from services.section_catalog import load_section_catalog
from services.sections_registry import load_sections_registry


def _callbacks(markup) -> list[str]:
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


def _button_texts(markup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


class FakeBot:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def send_message(self, **kwargs):
        self.calls.append(("send_message", kwargs))
        return SimpleNamespace(message_id=501)

    async def send_photo(self, **kwargs):
        self.calls.append(("send_photo", kwargs))
        return SimpleNamespace(message_id=502)

    async def send_video(self, **kwargs):
        self.calls.append(("send_video", kwargs))
        return SimpleNamespace(message_id=503)

    async def send_media_group(self, **kwargs):
        self.calls.append(("send_media_group", kwargs))
        return [SimpleNamespace(message_id=504), SimpleNamespace(message_id=505)]


class FakeMessage:
    def __init__(self) -> None:
        self.edits: list[dict] = []

    async def edit_text(self, text: str, **kwargs):
        self.edits.append({"text": text, **kwargs})


class FakeState:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


async def _publisher_smoke(post: dict, post_text: str) -> None:
    no_media_bot = FakeBot()
    no_media = await publish_premium_post_to_telegram(
        no_media_bot,
        post,
        post_text=post_text,
        publish_chat_id=int(Config.CHANNEL_ID),
        topic_id=17418,
    )
    assert no_media.message_ids == [501]
    assert no_media_bot.calls == [
        (
            "send_message",
            {
                "chat_id": int(Config.CHANNEL_ID),
                "text": post_text,
                "message_thread_id": 17418,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
    ]

    media_post = dict(post)
    media_post["media_list"] = json.dumps(
        [{"type": "photo", "file_id": "test-photo-id"}],
        ensure_ascii=False,
    )
    media_bot = FakeBot()
    with_media = await publish_premium_post_to_telegram(
        media_bot,
        media_post,
        post_text=post_text,
        publish_chat_id=int(Config.CHANNEL_ID),
        topic_id=17418,
    )
    assert with_media.message_ids == [502]
    assert media_bot.calls[0][0] == "send_photo"
    assert media_bot.calls[0][1]["message_thread_id"] == 17418
    assert media_bot.calls[0][1]["caption"] == post_text


async def _submission_smoke(raw_payload: dict) -> None:
    with tempfile.TemporaryDirectory(prefix="talk-to-me-smoke-") as tmp:
        smoke_db = Database(str(Path(tmp) / "smoke.db"))
        fake_bot = FakeBot()
        fake_message = FakeMessage()
        fake_state = FakeState()
        callback = SimpleNamespace(
            bot=fake_bot,
            message=fake_message,
            from_user=SimpleNamespace(
                id=991001,
                username="talk_test",
                first_name="Talk",
                last_name="Tester",
            ),
        )

        original_db = generic_flow.db
        generic_flow.db = smoke_db
        try:
            post_id = await generic_flow._submit_talk_to_me_for_moderation(
                callback,
                fake_state,
                section_name=TALK_TO_ME_SECTION_NAME,
                payload=raw_payload,
                media_list=[],
            )
        finally:
            generic_flow.db = original_db

        post = smoke_db.get_premium_post(post_id)
        assert post is not None
        assert post["mode"] == TALK_TO_ME_MODE
        assert post["status"] == "pending"
        assert post["payment_status"] == "pending"
        assert float(post["payment_amount"]) == 0.0
        assert post["admin_notes"] == "talk_to_me_moderation"
        assert post["message_id"] is None
        assert fake_state.cleared
        assert len(fake_bot.calls) == 2
        assert all(call[0] == "send_message" for call in fake_bot.calls)
        assert "Бесплатная публикация «Поговори со мной» — €0" in fake_bot.calls[1][1]["text"]
        assert fake_message.edits
        assert "отправлена на модерацию" in fake_message.edits[-1]["text"]


def run_smoke() -> None:
    project_root = Path(__file__).resolve().parent.parent
    groups_raw = json.loads(
        (project_root / "config" / "section_groups.json").read_text(encoding="utf-8")
    )
    serialized_groups = json.dumps(groups_raw, ensure_ascii=False)
    assert "https://t.me/Kak_odin" not in serialized_groups
    assert TALK_TO_ME_SECTION_NAME in serialized_groups

    assert MODE_TO_SECTION_NAME[TALK_TO_ME_MODE] == TALK_TO_ME_SECTION_NAME
    assert load_sections_registry().get_topic_id(TALK_TO_ME_SECTION_NAME) == 17418
    leisure = load_section_catalog().get_group("leisure")
    assert TALK_TO_ME_SECTION_NAME in leisure.sections
    leisure_markup = _sections_keyboard("leisure")
    talk_buttons = [
        button
        for row in leisure_markup.inline_keyboard
        for button in row
        if button.text == TALK_TO_ME_SECTION_NAME
    ]
    assert len(talk_buttons) == 1
    assert talk_buttons[0].callback_data == "section:generic:talk_to_me"
    assert talk_buttons[0].url is None

    schema = build_schema_registry().get_by_section(TALK_TO_ME_SECTION_NAME)
    assert [step.field_name for step in schema.steps if step.kind != "info"] == [
        "resides_in_portugal",
        "profile_description",
        "availability",
        "telegram",
        "phone_main",
        "phone_whatsapp",
        "name",
    ]

    talk = SchemaFlowAdapter(TALK_TO_ME_SECTION_NAME)
    assert talk.accept_answer("да").accepted
    assert talk.accept_answer("").accepted
    assert talk.accept_answer("Русский язык, будни после 18:00; не обсуждаю политику.").accepted
    assert talk.accept_answer("@talk_test").accepted
    assert talk.accept_answer("").accepted
    assert talk.accept_answer("").accepted
    assert talk.accept_answer("").accepted
    assert talk.state.is_finished

    raw_payload = talk.export_context()
    validation = validate_talk_to_me_payload(raw_payload)
    assert validation.ok, validation.message
    assert not validate_talk_to_me_payload({}).ok

    canonical = build_talk_to_me_listing_payload(raw_payload)
    assert canonical["description"].startswith("Общение:")
    assert canonical["telegram"] == "@talk_test"
    assert canonical["geo_tags"] == ""
    post_text = render_talk_to_me_listing_html(canonical)
    assert "Общение:" in post_text
    assert "@talk_test" in post_text

    preview_callbacks = _callbacks(_preview_kb(TALK_TO_ME_MODE))
    assert preview_callbacks == [
        "gs:confirm:talk_to_me",
        "gs:premium:talk_to_me",
        "gs:back:talk_to_me",
    ]
    assert "€20" not in " ".join(_button_texts(_preview_kb(TALK_TO_ME_MODE)))
    profile_step = next(step for step in schema.steps if step.field_name == "profile_description")
    assert "gs:skip:talk_to_me" in _callbacks(_step_kb(profile_step, TALK_TO_ME_MODE))

    post = {
        "id": 1,
        "mode": TALK_TO_ME_MODE,
        "action_type": "post",
        "cities": "[]",
        "description": canonical["description"],
        "social_media": "",
        "telegram_username": canonical["telegram"],
        "phone_main": "",
        "phone_whatsapp": "",
        "name": "",
        "media_list": "[]",
        "admin_notes": "talk_to_me_moderation",
    }
    plan = build_premium_publish_plan(post, Config)
    assert plan.topic_id == 17418
    assert plan.publish_chat_id == int(Config.CHANNEL_ID)
    assert plan.post_text == post_text
    assert not plan.is_baraholka_publish

    assert db._premium_post_ttl_days(TALK_TO_ME_MODE) is None
    assert premium_request_label(
        action_type="post", mode=TALK_TO_ME_MODE, payment_amount=0
    ) == "Бесплатная публикация «Поговори со мной» — €0"
    assert premium_post_status_label(
        {"mode": TALK_TO_ME_MODE, "status": "pending", "payment_status": "pending"}
    ) == "На модерации"
    actions = premium_post_action_rows(
        {"mode": TALK_TO_ME_MODE, "status": "published", "action_type": "post"}, 10
    )
    assert _button_texts(SimpleNamespace(inline_keyboard=actions)) == ["Удалить"]

    approval = build_approval_user_notification(
        post,
        message_link="https://t.me/proflistpt/17418/501",
        is_baraholka_publish=False,
    )
    rejection = build_rejection_user_notification(post)
    assert "Поговори со мной" in approval.text
    assert "Поговори со мной" in rejection.text

    asyncio.run(_publisher_smoke(post, post_text))
    asyncio.run(_submission_smoke(raw_payload))


if __name__ == "__main__":
    run_smoke()
    print("TALK_TO_ME_MODERATION_SMOKE=OK")
