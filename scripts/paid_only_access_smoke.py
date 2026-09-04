#!/usr/bin/env python3
"""Smoke coverage for paid-only account restrictions."""

from pathlib import Path
from tempfile import TemporaryDirectory

from database import Database
from handlers.generic_schema_flow import _preview_kb
from handlers.housing_schema_flow import _hs_preview_kb
from services.publication_access import PAID_ONLY_NOTICE, free_publication_availability


def _callbacks(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def _user(db: Database, telegram_id: int) -> int:
    return db.create_user(telegram_id, f"user{telegram_id}", "Test", None)


def main() -> None:
    with TemporaryDirectory() as tmp:
        db = Database(str(Path(tmp) / "paid-only.db"))
        regular_id = _user(db, 1001)
        restricted_id = _user(db, 1002)

        with db.get_connection() as conn:
            conn.execute(
                "UPDATE users SET paid_only_posts = 1 WHERE id = ?",
                (restricted_id,),
            )
            conn.commit()

        assert not db.is_paid_only_user(regular_id)
        assert not db.is_paid_only_telegram_user(1001)
        assert db.is_paid_only_user(restricted_id)
        assert db.is_paid_only_telegram_user(1002)
        assert free_publication_availability(db, regular_id) == (True, None)
        assert free_publication_availability(db, restricted_id) == (False, PAID_ONLY_NOTICE)

        regular_post = db.create_premium_post(
            user_id=regular_id,
            mode="reviews",
            cities="Lisboa",
            description="Regular free post",
            social_media="",
            telegram_username="user1001",
            phone_main="",
            phone_whatsapp="",
            name="",
            payment_amount=0,
        )
        assert regular_post > 0

        paid_post = db.create_premium_post(
            user_id=restricted_id,
            mode="job_offer",
            cities="Lisboa",
            description="Restricted user's paid post",
            social_media="",
            telegram_username="user1002",
            phone_main="+351910000002",
            phone_whatsapp="",
            name="Test",
            payment_amount=20,
        )
        assert paid_post > 0

        try:
            db.create_premium_post(
                user_id=restricted_id,
                mode="reviews",
                cities="Lisboa",
                description="Must not be inserted",
                social_media="",
                telegram_username="user1002",
                phone_main="",
                phone_whatsapp="",
                name="",
                payment_amount=0,
            )
        except PermissionError:
            pass
        else:
            raise AssertionError("restricted free moderation post was accepted")

        payload = {
            "description": "Must not be published",
            "social_links": "",
            "telegram": "user1002",
            "phone_main": "+351910000002",
            "phone_whatsapp": "",
            "contact_name": "Test",
        }
        for publish in (
            lambda: db.publish_free_generic_post(
                restricted_id, "job_offer", payload, "Lisboa", 1, -1001, 10
            ),
            lambda: db.publish_free_housing_post(
                restricted_id,
                "owner_real_estate",
                payload,
                "Lisboa",
                1,
                -1001,
                10,
                [],
                [1],
            ),
        ):
            try:
                publish()
            except PermissionError:
                pass
            else:
                raise AssertionError("restricted direct free publication was accepted")

        assert "gs:confirm:job_offer" not in _callbacks(
            _preview_kb("job_offer", can_publish_free=False)
        )
        assert "gs:premium:job_offer" in _callbacks(
            _preview_kb("job_offer", can_publish_free=False)
        )
        assert "hs:publish_free:owner_real_estate" not in _callbacks(
            _hs_preview_kb("owner_real_estate", can_publish_free=False)
        )
        assert "hs:publish_paid:owner_real_estate" in _callbacks(
            _hs_preview_kb("owner_real_estate", can_publish_free=False)
        )

    print("PAID_ONLY_ACCESS_SMOKE=OK")


if __name__ == "__main__":
    main()
