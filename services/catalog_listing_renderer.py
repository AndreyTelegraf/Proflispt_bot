"""Shared catalog listing HTML renderer."""

import html

from database import db
from services.geo import render_geo_tags


def _norm(value: object) -> str:
    if value is None:
        return ""
    clean = str(value).strip()
    if not clean:
        return ""
    if clean.lower() in {"нет", "no", "none"}:
        return ""
    return clean


def _split_lines(value: object) -> list[str]:
    clean = _norm(value)
    if not clean:
        return []
    return [part.strip() for part in clean.splitlines() if part.strip()]


def render_catalog_listing_html(payload: dict) -> str:
    lines: list[str] = []

    geo_tags = render_geo_tags(payload.get("geo_tags"))
    if geo_tags:
        lines.append(html.escape(geo_tags))

    description = _norm(payload.get("description"))
    if description:
        desc_lines: list[str | None] = []
        blank_seen = False
        for raw_line in description.splitlines():
            part = raw_line.strip()
            if part:
                desc_lines.append(part)
                blank_seen = False
            elif desc_lines and not blank_seen:
                desc_lines.append(None)
                blank_seen = True

        while desc_lines and desc_lines[-1] is None:
            desc_lines.pop()

        if desc_lines:
            first_written = False
            for part in desc_lines:
                if part is None:
                    lines.append("")
                    continue
                if not first_written:
                    lines.append("- " + html.escape(part))
                    first_written = True
                else:
                    lines.append(html.escape(part))

    for link in _split_lines(payload.get("social_links")):
        lines.append(f'<a href="{html.escape(link, quote=True)}">Ссылка</a>')

    telegram = _norm(payload.get("telegram"))
    if telegram:
        lines.append(html.escape(telegram))

    phone_main = _norm(payload.get("phone_main"))
    if phone_main:
        lines.append(html.escape(phone_main))

    phone_whatsapp = _norm(payload.get("phone_whatsapp"))
    if phone_whatsapp and phone_whatsapp != phone_main:
        lines.append(html.escape(phone_whatsapp))

    contact_name = _norm(payload.get("contact_name"))
    if contact_name:
        lines.append("- " + html.escape(contact_name))

    performer = _norm(payload.get("telegram"))
    if performer:
        try:
            idx = db.get_review_index_for_performer(performer)
            total = idx.get("total", 0)
            latest = idx.get("latest", [])
        except Exception:
            total, latest = 0, []

        if total > 0 and latest:
            if lines:
                lines.append("")
            lines.append(f"Отзывы ({total}):")

            start = total - len(latest) + 1
            for i, r in enumerate(latest):
                num = start + i
                link = f"https://t.me/proflistpt/{r['review_topic_id']}/{r['review_message_id']}"
                lines.append(f'- <a href="{html.escape(link, quote=True)}">Отзыв #{num}</a>')

    return "\n".join(lines).strip()
