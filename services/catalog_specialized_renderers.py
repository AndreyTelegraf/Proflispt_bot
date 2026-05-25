"""Specialized catalog HTML renderers shared by handlers and admin publishing."""

import html
import json

from services.catalog_listing_renderer import _norm, _split_lines
from services.geo import render_geo_tags


RENTAL_TAGS: dict[str, str] = {
    "short_term": "#короткосрок",
    "long_term": "#долгосрок",
}


def normalize_housing_geo_tags_from_db(value: object) -> str:
    if not value:
        return ""

    cities = value
    if isinstance(value, str):
        try:
            cities = json.loads(value)
        except Exception:
            raw = value.strip()
            if raw.startswith("[") and raw.endswith("]"):
                raw = raw[1:-1].strip()
            raw = raw.strip().strip("'").strip('"').strip()
            parts = [p.strip().strip("'").strip('"') for p in raw.split(",") if p.strip()]
            return " ".join(f"#{p.lstrip('#').lower()}" for p in parts if p)

    if isinstance(cities, list):
        return " ".join(
            f"#{str(x).strip().lstrip('#').lower()}"
            for x in cities
            if str(x).strip()
        )

    clean = str(cities).strip()
    return clean if clean.startswith("#") else f"#{clean.lstrip('#').lower()}"


def extract_housing_rental_term_from_post(post: dict) -> str:
    try:
        notes = json.loads(post.get("admin_notes") or "{}")
        return str(notes.get("rental_term") or "")
    except Exception:
        return ""


def build_housing_listing_payload_from_premium_post(post: dict) -> dict:
    return {
        "geo_tags": normalize_housing_geo_tags_from_db(post.get("cities")),
        "rental_term": extract_housing_rental_term_from_post(post),
        "description": post.get("description", ""),
        "social_links": post.get("social_media", ""),
        "telegram": post.get("telegram_username", ""),
        "phone_main": post.get("phone_main", ""),
        "phone_whatsapp": post.get("phone_whatsapp", ""),
        "contact_name": post.get("name", ""),
    }


def render_housing_listing_html(payload: dict) -> str:
    """Housing-specific render: appends rental_term tag to geo line, omits review links."""
    lines: list[str] = []

    geo_line_raw = render_geo_tags(payload.get("geo_tags"))
    rental_tag = RENTAL_TAGS.get(str(payload.get("rental_term", "")), "")

    if geo_line_raw:
        geo_line = html.escape(geo_line_raw)
        if rental_tag:
            geo_line += " " + html.escape(rental_tag)
        lines.append(geo_line)

    description = _norm(payload.get("description"))
    if description:
        dlines = [p.strip() for p in description.splitlines() if p.strip()]
        if dlines:
            lines.append("- " + html.escape(dlines[0]))
            for p in dlines[1:]:
                lines.append(html.escape(p))

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

    return "\n".join(lines).strip()


def render_review_listing_html(payload: dict) -> str:
    lines: list[str] = []

    geo = str(payload.get("geo_tags") or "").strip()
    if geo:
        tag = geo if geo.startswith("#") else f"#{geo.lstrip('#').lower()}"
        lines.append(html.escape(tag))

    performer = str(payload.get("performer_contacts") or "").strip()
    if performer:
        uname = performer if performer.startswith("@") else f"@{performer.lstrip('@')}"
        lines.append(f"Исполнитель: {html.escape(uname)}")

    description = str(payload.get("description") or "").strip()
    if description:
        dlines = [p.strip() for p in description.splitlines() if p.strip()]
        if dlines:
            lines.append("- " + html.escape(dlines[0]))
            for p in dlines[1:]:
                lines.append(html.escape(p))

    author = str(payload.get("author_telegram") or "").strip()
    if author:
        uname = author if author.startswith("@") else f"@{author.lstrip('@')}"
        lines.append(f"Автор: {html.escape(uname)}")

    return "\n".join(lines).strip()


def build_review_listing_html_from_premium_post(post: dict) -> str:
    cities_raw = post.get("cities")
    geo_tags = ""
    if cities_raw:
        try:
            cities = json.loads(cities_raw) if isinstance(cities_raw, str) else cities_raw
            if isinstance(cities, list):
                geo_tags = " ".join(
                    f"#{str(x).strip().lstrip('#').lower()}"
                    for x in cities
                    if str(x).strip()
                )
            else:
                geo_tags = str(cities_raw).strip()
        except Exception:
            geo_tags = str(cities_raw).strip()

    return render_review_listing_html({
        "geo_tags": geo_tags,
        "description": post.get("description", ""),
        "performer_contacts": post.get("social_media", ""),
        "author_telegram": post.get("telegram_username", ""),
    })
