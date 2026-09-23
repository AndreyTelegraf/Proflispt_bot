from __future__ import annotations

import os
import sys
import tempfile
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


with tempfile.TemporaryDirectory() as runtime_dir:
    os.chdir(runtime_dir)

    config_module = types.ModuleType("config")
    config_module.Config = type("Config", (), {})
    sys.modules.setdefault("config", config_module)

    from database import Database

    test_db = Database(str(Path(runtime_dir) / "publication-idempotency.db"))
    user_id = test_db.create_user(telegram_id=900001, username="race_test")

    request_id = test_db.create_premium_post(
        user_id=user_id,
        mode="owner_real_estate",
        cities="[]",
        description="Atomic publication claim",
        telegram_username="@race_test",
        phone_main="+351900000001",
        name="Race Test",
        media_list=[],
        payment_amount=10,
        action_type="post",
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        claims = list(
            executor.map(
                lambda _: test_db.claim_premium_post_for_publication(request_id, 777),
                range(8),
            )
        )

    assert claims.count(True) == 1, claims
    assert claims.count(False) == 7, claims
    claimed = test_db.get_premium_post(request_id)
    assert claimed["status"] == "publishing"
    assert claimed["payment_status"] == "approved"

    source_id = test_db.create_premium_post(
        user_id=user_id,
        mode="owner_real_estate",
        cities="[]",
        description="Baraholka source",
        telegram_username="@race_test",
        phone_main="+351900000002",
        name="Race Test",
        media_list=[],
        payment_amount=10,
        action_type="post",
    )
    assert test_db.approve_premium_post(source_id, 777)
    assert test_db.update_premium_post_publication(
        source_id,
        message_id=1001,
        chat_id=-1001000000000,
        topic_id=8490,
        published_message_ids=[1001],
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        requests = list(
            executor.map(
                lambda _: test_db.create_baraholka_housing_repost_from_post(
                    source_id,
                    user_id,
                ),
                range(8),
            )
        )

    request_ids = {post_id for post_id, _created in requests}
    created_flags = [_created for _post_id, _created in requests]
    assert len(request_ids) == 1, requests
    assert created_flags.count(True) == 1, requests
    assert created_flags.count(False) == 7, requests

    rejection_id = test_db.create_premium_post(
        user_id=user_id,
        mode="owner_real_estate",
        cities="[]",
        description="Moderation race",
        telegram_username="@race_test",
        phone_main="+351900000003",
        name="Race Test",
        media_list=[],
        payment_amount=10,
        action_type="post",
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda action: (
                    test_db.claim_premium_post_for_publication(rejection_id, 777)
                    if action == "approve"
                    else test_db.reject_pending_premium_post(
                        rejection_id,
                        777,
                        "Rejected in race test",
                    )
                ),
                ["approve", "reject"],
            )
        )

    assert results.count(True) == 1, results

print("premium_publication_idempotency_smoke OK")
