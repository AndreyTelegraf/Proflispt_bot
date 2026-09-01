from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

with tempfile.TemporaryDirectory() as runtime_dir:
    previous_cwd = Path.cwd()
    os.chdir(runtime_dir)
    try:
        from database import Database
        from services.directory_post_guard import check_pending_directory_post

        test_db = Database(str(Path(runtime_dir) / "resubmit.db"))
        user_id = test_db.create_user(telegram_id=1001, username="resubmit_user")

        published_free_id = test_db.create_premium_post(
            user_id=user_id,
            mode="owner_real_estate",
            cities="[]",
            description="Published free listing",
            telegram_username="@resubmit_user",
            phone_main="+351000000000",
            name="Resubmit User",
            media_list=[],
            payment_amount=0,
            action_type="post",
        )
        assert test_db.approve_premium_post(published_free_id, admin_id=777)
        assert test_db.update_premium_post_publication(
            published_free_id,
            message_id=5001,
            chat_id=-1001000000000,
            topic_id=8490,
            published_message_ids=[5001],
        )

        allowed, message = asyncio.run(
            check_pending_directory_post(
                test_db,
                user_id=user_id,
                mode="owner_real_estate",
                phone_main="+351000000000",
            )
        )
        assert allowed
        assert message is None

        request_id = test_db.create_premium_post(
            user_id=user_id,
            mode="owner_real_estate",
            cities="[]",
            description="First paid draft",
            telegram_username="@resubmit_user",
            phone_main="+351000000000",
            name="Resubmit User",
            media_list=[],
            payment_amount=10,
            action_type="post",
        )

        allowed, _ = asyncio.run(
            check_pending_directory_post(
                test_db,
                user_id=user_id,
                mode="owner_real_estate",
                phone_main="+351000000000",
            )
        )
        assert not allowed

        assert test_db.reject_premium_post(
            request_id,
            admin_id=777,
            admin_notes="Rejected for editing",
        )
        rejected = test_db.get_premium_post(request_id)
        assert rejected["payment_status"] == "rejected"
        assert rejected["status"] == "rejected"

        allowed, message = asyncio.run(
            check_pending_directory_post(
                test_db,
                user_id=user_id,
                mode="owner_real_estate",
                phone_main="+351000000000",
            )
        )
        assert allowed
        assert message is None

        legacy_request_id = test_db.create_premium_post(
            user_id=user_id,
            mode="owner_real_estate",
            cities="[]",
            description="Legacy rejected draft",
            telegram_username="@resubmit_user",
            phone_main="+351000000000",
            name="Resubmit User",
            media_list=[],
            payment_amount=10,
            action_type="post",
        )
        with test_db.get_connection() as conn:
            conn.execute(
                """
                UPDATE premium_posts
                SET payment_status = 'rejected', status = 'pending'
                WHERE id = ?
                """,
                (legacy_request_id,),
            )
            conn.commit()

        allowed, message = asyncio.run(
            check_pending_directory_post(
                test_db,
                user_id=user_id,
                mode="owner_real_estate",
                phone_main="+351000000000",
            )
        )
        assert allowed
        assert message is None

        second_request_id = test_db.create_premium_post(
            user_id=user_id,
            mode="owner_real_estate",
            cities="[]",
            description="Corrected paid draft",
            telegram_username="@resubmit_user",
            phone_main="+351000000000",
            name="Resubmit User",
            media_list=[],
            payment_amount=10,
            action_type="post",
        )
        assert second_request_id > legacy_request_id
    finally:
        os.chdir(previous_cwd)

print("PAID_REJECTION_RESUBMIT_SMOKE=OK")
