from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.directory_username_http_audit import (
    DirectoryUsernameAuditIssue,
    build_directory_username_audit_report,
    normalize_telegram_username,
    username_slug,
)

assert normalize_telegram_username("@Kak_odin") == "@Kak_odin"
assert normalize_telegram_username("https://t.me/Kak_odin") == "@Kak_odin"
assert normalize_telegram_username("telegram.me/Kak_odin/") == "@Kak_odin"
assert normalize_telegram_username("") == ""
assert username_slug("@Kak_odin") == "Kak_odin"

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
)

assert "Проверено объявлений: 2" in report
assert "Проблемных контактов: 1" in report
assert "@missing_user" in report
assert "Грузовые перевозки #123" in report

print("directory_username_http_audit_smoke OK")
