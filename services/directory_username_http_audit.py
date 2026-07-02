"""Read-only public t.me username audit for published directory posts."""

from __future__ import annotations

import html
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from config import Config
from services.admin_moderation_notice import resolve_admin_moderation_chat_id
from services.catalog_modes import get_section_name_for_mode
from services.directory_links import directory_message_url


@dataclass(frozen=True)
class DirectoryUsernameAuditIssue:
    post_id: int
    username: str
    reason: str
    section_name: str
    display_title: str
    post_url: str | None


def normalize_telegram_username(value: object) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    clean = clean.split()[0].strip()
    for prefix in ("https://t.me/", "http://t.me/", "https://telegram.me/", "http://telegram.me/", "t.me/", "telegram.me/"):
        if clean.lower().startswith(prefix):
            clean = clean[len(prefix):]
            break
    clean = clean.lstrip("@").strip("/")
    if not clean:
        return ""
    return "@" + clean


def username_slug(username: str) -> str:
    return normalize_telegram_username(username).lstrip("@")


def _loads_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _compact(value: object, *, limit: int = 80) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return "Объявление"
    if len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _post_url(row: dict[str, Any]) -> str | None:
    message_id = row.get("message_id")
    published_ids = _loads_list(row.get("published_message_ids"))
    if published_ids:
        message_id = published_ids[0]
    if not message_id:
        return None
    return directory_message_url(message_id, row.get("topic_id"))


def load_published_directory_contact_rows(db, *, limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT
            pp.id,
            pp.mode,
            pp.description,
            pp.telegram_username,
            pp.message_id,
            pp.topic_id,
            pp.published_message_ids,
            pp.created_at,
            pp.status,
            pp.payment_status,
            pp.action_type
        FROM premium_posts pp
        WHERE pp.status = 'published'
          AND pp.payment_status = 'approved'
          AND pp.mode != 'reviews'
          AND COALESCE(pp.telegram_username, '') != ''
          AND pp.message_id IS NOT NULL
        ORDER BY datetime(pp.created_at) DESC, pp.id DESC
    """
    params: tuple = ()
    if limit is not None:
        sql += "\n        LIMIT ?"
        params = (int(limit),)

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def _issue_from_row(row: dict[str, Any], *, reason: str) -> DirectoryUsernameAuditIssue:
    mode = str(row.get("mode") or "")
    return DirectoryUsernameAuditIssue(
        post_id=int(row["id"]),
        username=normalize_telegram_username(row.get("telegram_username")),
        reason=reason,
        section_name=get_section_name_for_mode(mode) or mode or "Раздел",
        display_title=_compact(row.get("description")),
        post_url=_post_url(row),
    )


def check_public_tme_username(username: str, *, timeout: float = 8.0) -> tuple[bool, str | None]:
    slug = username_slug(username)
    if not slug:
        return False, "empty_username"

    url = f"https://t.me/{slug}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ProflistPTBot/1.0; +https://t.me/proflistpt)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 0) or 0)
            body = response.read(200000).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False, "t.me returned 404"
        return False, f"t.me HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, f"t.me URL error: {exc.reason}"
    except TimeoutError:
        return False, "t.me timeout"

    if status >= 400:
        return False, f"t.me HTTP {status}"

    lower = body.lower()
    not_found_markers = [
        "tgme_page_extra\">if you have <strong>telegram</strong>, you can contact",
        "tgme_page_description\">if you have <strong>telegram</strong>, you can contact",
        "username not found",
        "this channel is unavailable",
    ]
    if "tgme_page_title" not in lower and "tgme_page_wrap" not in lower:
        return False, "unexpected t.me page"

    if any(marker in lower for marker in not_found_markers):
        return False, "t.me page has not-found marker"

    return True, None


def audit_directory_usernames(db, *, limit: int | None = None) -> tuple[int, list[DirectoryUsernameAuditIssue]]:
    rows = load_published_directory_contact_rows(db, limit=limit)
    issues: list[DirectoryUsernameAuditIssue] = []

    checked_cache: dict[str, tuple[bool, str | None]] = {}
    for row in rows:
        username = normalize_telegram_username(row.get("telegram_username"))
        if username not in checked_cache:
            checked_cache[username] = check_public_tme_username(username)

        ok, reason = checked_cache[username]
        if not ok:
            issues.append(_issue_from_row(row, reason=reason or "unknown"))

    return len(rows), issues


def build_directory_username_audit_report(*, checked_count: int, issues: list[DirectoryUsernameAuditIssue]) -> str:
    lines = [
        "<b>Проверка Telegram-контактов Справочника</b>",
        "",
        f"Проверено объявлений: {checked_count}",
        f"Проблемных контактов: {len(issues)}",
    ]

    if not issues:
        lines.extend(["", "Проблемных Telegram username не найдено."])
        return "\n".join(lines)

    lines.append("")
    for issue in issues[:80]:
        lines.append(f"❌ {html.escape(issue.username)} — {html.escape(issue.section_name)} #{issue.post_id}")
        lines.append(html.escape(issue.display_title))
        if issue.post_url:
            lines.append(html.escape(issue.post_url))
        lines.append(f"Причина: {html.escape(issue.reason)}")
        lines.append("")

    if len(issues) > 80:
        lines.append(f"Показаны первые 80 из {len(issues)} проблемных контактов.")

    return "\n".join(lines).strip()


async def send_directory_username_audit_report(bot, db, *, fallback_admin_chat_id: int | None = None, limit: int | None = None) -> tuple[int, int]:
    checked_count, issues = audit_directory_usernames(db, limit=limit)
    report = build_directory_username_audit_report(checked_count=checked_count, issues=issues)
    recipient = resolve_admin_moderation_chat_id(
        fallback_admin_chat_id if fallback_admin_chat_id is not None else Config.ADMIN_IDS[0]
    )

    chunks: list[str] = []
    text = report
    while len(text) > 3900:
        cut = text.rfind("\n", 0, 3900)
        if cut <= 0:
            cut = 3900
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    chunks.append(text)

    for chunk in chunks:
        await bot.send_message(
            chat_id=recipient,
            text=chunk,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    return checked_count, len(issues)
