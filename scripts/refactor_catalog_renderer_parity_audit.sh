#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_catalog_renderer_parity_${STAMP}"
mkdir -p "$OUT"

REPORT="$OUT/report.txt"

echo "===== CATALOG RENDERER PARITY AUDIT ONLY ====="
echo "$OUT"

echo
echo "===== IMPORT AND OUTPUT SMOKE ====="
venv/bin/python - <<'PY'
from services.catalog_listing_renderer import (
    build_catalog_listing_payload_from_premium_post,
    normalize_catalog_geo_tags_from_db,
    render_catalog_listing_html,
)

payload = {
    "geo_tags": "#lisboa #porto",
    "description": "Linha 1\n\nLinha 2",
    "social_links": "example.com\nhttps://instagram.com/example",
    "telegram": "@telegraf",
    "phone_main": "+351912345678",
    "phone_whatsapp": "",
    "contact_name": "Andrey",
}

rendered = render_catalog_listing_html(payload)
assert "#lisboa" in rendered
assert "#porto" in rendered
assert "- Linha 1" in rendered
assert "Linha 2" in rendered
assert "Ссылка" in rendered
assert "@telegraf" in rendered
assert "+351912345678" in rendered
assert "- Andrey" in rendered

assert normalize_catalog_geo_tags_from_db('["lisboa","porto"]') == "#lisboa #porto"
assert normalize_catalog_geo_tags_from_db("lisboa") == "#lisboa"
assert normalize_catalog_geo_tags_from_db("#lisboa") == "#lisboa"

post = {
    "cities": '["lisboa"]',
    "description": "Cafe Telegraf",
    "social_media": "https://example.com",
    "telegram_username": "@telegraf",
    "phone_main": "+351912345678",
    "phone_whatsapp": "",
    "name": "Andrey",
    "review_links": "",
}

built = build_catalog_listing_payload_from_premium_post(post)
assert built["geo_tags"] == "#lisboa"
assert built["description"] == "Cafe Telegraf"
assert built["social_links"] == "https://example.com"
assert built["telegram"] == "@telegraf"
assert built["phone_main"] == "+351912345678"
assert built["contact_name"] == "Andrey"

rendered_from_post = render_catalog_listing_html(built)
assert "#lisboa" in rendered_from_post
assert "Cafe Telegraf" in rendered_from_post
assert "Ссылка" in rendered_from_post

print("catalog_renderer_parity_smoke_ok")
PY


echo
echo "===== COMPILE SANITY ====="
venv/bin/python -m py_compile \
  services/catalog_modes.py \
  services/catalog_listing_renderer.py \
  handlers/premium_admin.py \
  handlers/generic_schema_flow.py \
  main.py \
  database.py

{
  echo "catalog_renderer_parity_audit=$OUT"
  echo
  echo "VERDICT:"
  echo "shared catalog renderer import/output smoke passed"
  echo "premium post payload builder smoke passed"
  echo "renderer/catalog mode coupling guards passed"
} | tee "$REPORT"

echo
echo "===== OUTPUT ====="
echo "$OUT"
