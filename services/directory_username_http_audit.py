"""Read-only public t.me username audit for published directory posts."""

from __future__ import annotations

import asyncio
import html
import json
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from functools import partial
from typing import Any

from config import Config
from services.catalog_modes import get_section_name_for_mode
from services.directory_links import directory_message_url, telegram_message_url


@dataclass(frozen=True)
class DirectoryUsernameAuditIssue:
    post_id: int
    username: str
    reason: str
    section_name: str
    display_title: str
    post_url: str | None
    chat_id: int | None = None
    message_id: int | None = None
    topic_id: int | None = None
    owner_telegram_id: int | None = None
    owner_username: str | None = None


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


def _message_id(row: dict[str, Any]) -> int | None:
    message_id = row.get("message_id")
    published_ids = _loads_list(row.get("published_message_ids"))
    if published_ids:
        message_id = published_ids[0]
    return int(message_id) if message_id else None


def _post_url(row: dict[str, Any], *, chat_username: str | None = None) -> str | None:
    message_id = _message_id(row)
    if not message_id:
        return None

    if chat_username:
        return telegram_message_url(chat_username, message_id, row.get("topic_id"))

    chat_id = row.get("chat_id")
    if chat_id and int(chat_id) == int(Config.CHANNEL_ID):
        return directory_message_url(message_id, row.get("topic_id"))

    chat_id_text = str(chat_id or "")
    if chat_id_text.startswith("-100"):
        internal_id = chat_id_text[4:]
        topic_id = row.get("topic_id")
        if topic_id:
            return f"https://t.me/c/{internal_id}/{topic_id}/{message_id}"
        return f"https://t.me/c/{internal_id}/{message_id}"

    return directory_message_url(message_id, row.get("topic_id"))


def load_published_directory_contact_rows(db, *, limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT
            pp.id,
            pp.mode,
            pp.description,
            pp.telegram_username,
            pp.message_id,
            pp.chat_id,
            pp.topic_id,
            pp.published_message_ids,
            pp.created_at,
            pp.status,
            pp.payment_status,
            pp.action_type,
            u.telegram_id AS owner_telegram_id,
            u.username AS owner_username
        FROM premium_posts pp
        JOIN users u ON u.id = pp.user_id
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
        chat_id=int(row["chat_id"]) if row.get("chat_id") else None,
        message_id=_message_id(row),
        topic_id=int(row["topic_id"]) if row.get("topic_id") else None,
        owner_telegram_id=int(row["owner_telegram_id"]) if row.get("owner_telegram_id") else None,
        owner_username=normalize_telegram_username(row.get("owner_username")),
    )


def _check_public_tme_username_once(username: str, *, timeout: float) -> tuple[bool | None, str | None]:
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
        return None, f"t.me HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return None, f"t.me URL error: {exc.reason}"
    except TimeoutError:
        return None, "t.me timeout"
    except OSError as exc:
        return None, f"t.me connection error: {exc}"
    except Exception as exc:
        return None, f"t.me check error: {type(exc).__name__}: {exc}"

    if status >= 400:
        return None, f"t.me HTTP {status}"

    lower = body.lower()
    plain_text = " ".join(
        re.sub(r"<[^>]+>", " ", html.unescape(lower)).split()
    )
    description_blocks = re.findall(
        r'<div\s+class="[^"]*\btgme_page_description\b[^"]*"[^>]*>(.*?)</div>',
        lower,
        flags=re.DOTALL,
    )
    description_text = " ".join(
        re.sub(r"<[^>]+>", " ", html.unescape(block)).strip()
        for block in description_blocks
    )
    description_text = " ".join(description_text.split())

    if re.search(r"if you have telegram\s*,\s*you can contact", description_text):
        return None, "t.me returned an ambiguous generic contact page"

    if "username not found" in plain_text or "this channel is unavailable" in plain_text:
        return False, "t.me page has not-found marker"

    if "tgme_page_title" not in lower:
        return None, "unexpected t.me page"

    return True, None


def check_public_tme_username(
    username: str,
    *,
    timeout: float = 8.0,
    attempts: int = 3,
    retry_delay: float = 2.0,
) -> tuple[bool | None, str | None]:
    """Return True for valid, False for confirmed invalid, None for unavailable.

    Transport errors and unexpected responses are retried and never presented as
    proof that a Telegram username is invalid.
    """
    if not username_slug(username):
        return False, "empty_username"

    attempts = max(1, int(attempts))
    invalid_count = 0
    last_reason: str | None = None

    for attempt in range(attempts):
        ok, reason = _check_public_tme_username_once(username, timeout=timeout)
        if ok is True:
            return True, None
        if ok is False:
            invalid_count += 1
        last_reason = reason
        if attempt + 1 < attempts and retry_delay > 0:
            time.sleep(retry_delay * (2**attempt))

    if invalid_count == attempts:
        return False, f"{last_reason or 't.me username not found'} confirmed by {attempts} attempts"

    return None, (
        f"{last_reason or 'temporary t.me error'}; inconclusive after {attempts} attempts "
        f"({invalid_count} not-found responses)"
    )


def _meta_content(body: str, property_name: str) -> str:
    matches = re.findall(
        rf'<meta\s+property="{re.escape(property_name)}"\s+content="([^"]*)"',
        body,
        flags=re.IGNORECASE,
    )
    return " ".join(html.unescape(value) for value in matches).strip()


def _check_public_tme_post_once(
    post_url: str,
    *,
    expected_username: str,
    timeout: float,
) -> tuple[bool | None, str | None]:
    request = urllib.request.Request(
        post_url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ProflistPTBot/1.0; +https://t.me/proflistpt)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 0) or 0)
            body = response.read(300000).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False, "Telegram publication returned 404"
        return None, f"Telegram publication HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return None, f"Telegram publication URL error: {exc.reason}"
    except TimeoutError:
        return None, "Telegram publication timeout"
    except OSError as exc:
        return None, f"Telegram publication connection error: {exc}"
    except Exception as exc:
        return None, f"Telegram publication check error: {type(exc).__name__}: {exc}"

    if status >= 400:
        return None, f"Telegram publication HTTP {status}"

    title = " ".join(_meta_content(body, "og:title").split())
    description = " ".join(_meta_content(body, "og:description").split())
    expected_slug = username_slug(expected_username).casefold()
    description_folded = description.casefold()

    if expected_slug and f"@{expected_slug}" in description_folded:
        return True, None
    if " in " in title.casefold() and description:
        return True, None
    if "tgme_page_title" in body.lower():
        return False, "Telegram publication is absent; channel landing page returned"
    if title.casefold() == "telegram – a new era of messaging":
        return False, "Telegram publication is absent"
    return None, "unexpected Telegram publication page"


def check_public_tme_post(
    post_url: str,
    *,
    expected_username: str,
    timeout: float = 8.0,
    attempts: int = 3,
    retry_delay: float = 2.0,
) -> tuple[bool | None, str | None]:
    attempts = max(1, int(attempts))
    missing_count = 0
    last_reason: str | None = None

    for attempt in range(attempts):
        ok, reason = _check_public_tme_post_once(
            post_url,
            expected_username=expected_username,
            timeout=timeout,
        )
        if ok is True:
            return True, None
        if ok is False:
            missing_count += 1
        last_reason = reason
        if attempt + 1 < attempts and retry_delay > 0:
            time.sleep(retry_delay * (2**attempt))

    if missing_count == attempts:
        return False, f"{last_reason or 'Telegram publication is absent'} confirmed by {attempts} attempts"

    return None, (
        f"{last_reason or 'temporary Telegram publication error'}; "
        f"inconclusive after {attempts} attempts ({missing_count} missing responses)"
    )


def audit_directory_usernames(
    db,
    *,
    limit: int | None = None,
    max_workers: int = 4,
    confirmation_workers: int = 2,
    confirmation_cooldown: float = 5.0,
) -> tuple[int, list[DirectoryUsernameAuditIssue], list[DirectoryUsernameAuditIssue]]:
    rows = load_published_directory_contact_rows(db, limit=limit)
    issues: list[DirectoryUsernameAuditIssue] = []
    unavailable: list[DirectoryUsernameAuditIssue] = []

    usernames_by_key: dict[str, str] = {}
    for row in rows:
        username = normalize_telegram_username(row.get("telegram_username"))
        usernames_by_key.setdefault(username.casefold(), username)

    checked_cache: dict[str, tuple[bool | None, str | None]] = {}
    if usernames_by_key:
        worker_count = max(1, min(int(max_workers), len(usernames_by_key)))
        keys = list(usernames_by_key)
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="tme-audit") as executor:
            initial_check = partial(check_public_tme_username, attempts=1, retry_delay=0)
            results = executor.map(initial_check, (usernames_by_key[key] for key in keys))
            checked_cache = dict(zip(keys, results))

        confirmation_keys = [key for key in keys if checked_cache[key][0] is not True]
        if confirmation_keys:
            if confirmation_cooldown > 0:
                time.sleep(confirmation_cooldown)
            worker_count = max(1, min(int(confirmation_workers), len(confirmation_keys)))
            with ThreadPoolExecutor(
                max_workers=worker_count,
                thread_name_prefix="tme-audit-confirm",
            ) as executor:
                confirmation_results = executor.map(
                    check_public_tme_username,
                    (usernames_by_key[key] for key in confirmation_keys),
                )
                checked_cache.update(zip(confirmation_keys, confirmation_results))

    for row in rows:
        username = normalize_telegram_username(row.get("telegram_username"))
        ok, reason = checked_cache[username.casefold()]
        if ok is False:
            issues.append(_issue_from_row(row, reason=reason or "unknown"))
        elif ok is None:
            unavailable.append(_issue_from_row(row, reason=reason or "temporary t.me error"))

    return len(rows), issues, unavailable


async def _get_chat_username(bot, chat_id_or_username) -> tuple[str | None, str | None]:
    try:
        chat = await bot.get_chat(chat_id_or_username)
        return normalize_telegram_username(getattr(chat, "username", None)), None
    except Exception as exc:
        return None, f"Bot API error: {type(exc).__name__}"


async def verify_directory_username_audit_candidates(
    bot,
    issues: list[DirectoryUsernameAuditIssue],
    unavailable: list[DirectoryUsernameAuditIssue],
    *,
    post_check_workers: int = 4,
) -> tuple[
    list[DirectoryUsernameAuditIssue],
    list[DirectoryUsernameAuditIssue],
    list[DirectoryUsernameAuditIssue],
]:
    """Verify suspicious contacts only for publications that still exist.

    Public t.me contact pages can temporarily return the same generic page for
    working and missing usernames. A negative contact result is therefore never
    final until the publication is confirmed live and Bot API owner data either
    validates the username or proves that the owner's username changed.
    """
    candidates = issues + unavailable
    if not candidates:
        return [], [], []

    chat_username_cache: dict[int, str | None] = {}
    for chat_id in sorted({item.chat_id for item in candidates if item.chat_id}):
        chat_username, _ = await _get_chat_username(bot, chat_id)
        chat_username_cache[int(chat_id)] = chat_username

    corrected_candidates: list[DirectoryUsernameAuditIssue] = []
    for item in candidates:
        chat_username = chat_username_cache.get(int(item.chat_id)) if item.chat_id else None
        row = {
            "message_id": item.message_id,
            "chat_id": item.chat_id,
            "topic_id": item.topic_id,
        }
        corrected_candidates.append(
            replace(item, post_url=_post_url(row, chat_username=chat_username))
        )

    semaphore = asyncio.Semaphore(max(1, int(post_check_workers)))

    async def check_post(item: DirectoryUsernameAuditIssue):
        if not item.post_url:
            return item, None, "Publication URL is unavailable"
        async with semaphore:
            ok, reason = await asyncio.to_thread(
                check_public_tme_post,
                item.post_url,
                expected_username=item.username,
            )
        return item, ok, reason

    post_results = await asyncio.gather(*(check_post(item) for item in corrected_candidates))
    live_candidates: list[DirectoryUsernameAuditIssue] = []
    verified_unavailable: list[DirectoryUsernameAuditIssue] = []
    stale_publications: list[DirectoryUsernameAuditIssue] = []

    for item, post_ok, post_reason in post_results:
        if post_ok is True:
            live_candidates.append(item)
        elif post_ok is False:
            stale_publications.append(
                replace(item, reason=post_reason or "Telegram publication is absent")
            )
        else:
            verified_unavailable.append(
                replace(item, reason=post_reason or "Publication could not be verified")
            )

    owner_cache: dict[int, tuple[str | None, str | None]] = {}
    for owner_id in sorted({item.owner_telegram_id for item in live_candidates if item.owner_telegram_id}):
        owner_cache[int(owner_id)] = await _get_chat_username(bot, owner_id)

    contact_cache: dict[str, tuple[str | None, str | None]] = {}
    confirmed: list[DirectoryUsernameAuditIssue] = []
    for item in live_candidates:
        contact_key = item.username.casefold()
        owner_current, owner_error = owner_cache.get(
            int(item.owner_telegram_id),
            (None, "Owner Telegram ID is unavailable"),
        ) if item.owner_telegram_id else (None, "Owner Telegram ID is unavailable")

        if owner_current and owner_current.casefold() == contact_key:
            continue

        if contact_key not in contact_cache:
            contact_cache[contact_key] = await _get_chat_username(bot, item.username)
        resolved_contact, _ = contact_cache[contact_key]
        if resolved_contact and resolved_contact.casefold() == contact_key:
            continue

        owner_was_contact = bool(
            item.owner_username
            and item.owner_username.casefold() == contact_key
        )
        if owner_was_contact and owner_error is None:
            if owner_current:
                reason = (
                    f"Bot API confirms owner username changed from {item.username} "
                    f"to {owner_current}"
                )
            else:
                reason = f"Bot API confirms owner no longer has username {item.username}"
            confirmed.append(replace(item, reason=reason))
            continue

        reason = item.reason
        if owner_error:
            reason = f"{reason}; {owner_error}"
        else:
            reason = f"{reason}; negative result not confirmed by Bot API"
        verified_unavailable.append(replace(item, reason=reason))

    return confirmed, verified_unavailable, stale_publications


async def audit_directory_usernames_verified(
    bot,
    db,
    *,
    limit: int | None = None,
) -> tuple[
    int,
    list[DirectoryUsernameAuditIssue],
    list[DirectoryUsernameAuditIssue],
    list[DirectoryUsernameAuditIssue],
]:
    checked_count, issues, unavailable = await asyncio.to_thread(
        audit_directory_usernames,
        db,
        limit=limit,
    )
    confirmed, verified_unavailable, stale_publications = (
        await verify_directory_username_audit_candidates(bot, issues, unavailable)
    )
    return checked_count, confirmed, verified_unavailable, stale_publications


def build_directory_username_audit_report(
    *,
    checked_count: int,
    issues: list[DirectoryUsernameAuditIssue],
    unavailable: list[DirectoryUsernameAuditIssue] | None = None,
    stale_publications: list[DirectoryUsernameAuditIssue] | None = None,
) -> str:
    unavailable = unavailable or []
    stale_publications = stale_publications or []
    lines = [
        "<b>Проверка Telegram-контактов Справочника</b>",
        "",
        f"Записей со статусом «опубликовано» в базе: {checked_count}",
        f"Подтверждённо неработающих контактов в доступных объявлениях: {len(issues)}",
        f"Временно не удалось проверить: {len(unavailable)}",
        f"Пропущено отсутствующих публикаций: {len(stale_publications)}",
    ]

    if stale_publications:
        lines.extend([
            "",
            "Отсутствующие в Telegram публикации не считаются объявлениями "
            "с неработающим контактом. База автоматически не изменялась.",
        ])

    if not issues and not unavailable:
        lines.extend(["", "Все проверенные Telegram username работают."])
        return "\n".join(lines)

    if issues:
        lines.extend(["", "<b>Подтверждённо неработающие:</b>"])
        for issue in issues[:80]:
            lines.append(f"❌ {html.escape(issue.username)} — {html.escape(issue.section_name)} #{issue.post_id}")
            lines.append(html.escape(issue.display_title))
            if issue.post_url:
                lines.append(html.escape(issue.post_url))
            lines.append(f"Причина: {html.escape(issue.reason)}")
            lines.append("")

        if len(issues) > 80:
            lines.append(f"Показаны первые 80 из {len(issues)} неработающих контактов.")

    if unavailable:
        lines.extend([
            "",
            "<b>Временные ошибки проверки:</b>",
            "Эти контакты не помечены как неработающие.",
        ])
        for issue in unavailable[:80]:
            lines.append(f"⚠️ {html.escape(issue.username)} — {html.escape(issue.section_name)} #{issue.post_id}")
            lines.append(html.escape(issue.display_title))
            if issue.post_url:
                lines.append(html.escape(issue.post_url))
            lines.append(f"Причина: {html.escape(issue.reason)}")
            lines.append("")

        if len(unavailable) > 80:
            lines.append(f"Показаны первые 80 из {len(unavailable)} временно непроверенных контактов.")

    return "\n".join(lines).strip()


async def send_directory_username_audit_report(bot, db, *, fallback_admin_chat_id: int | None = None, limit: int | None = None) -> tuple[int, int, int, int]:
    checked_count, issues, unavailable, stale_publications = await audit_directory_usernames_verified(
        bot,
        db,
        limit=limit,
    )
    report = build_directory_username_audit_report(
        checked_count=checked_count,
        issues=issues,
        unavailable=unavailable,
        stale_publications=stale_publications,
    )
    recipient = int(
        getattr(Config, "ADMIN_MODERATION_CHAT_ID", 0)
        or fallback_admin_chat_id
        or Config.ADMIN_IDS[0]
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

    return checked_count, len(issues), len(unavailable), len(stale_publications)
