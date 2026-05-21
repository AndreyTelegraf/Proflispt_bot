#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_catalog_modes_coupling_${STAMP}"
mkdir -p "$OUT"

FORBIDDEN="$OUT/forbidden_matches.txt"
REPORT="$OUT/report.txt"

echo "===== CATALOG MODES COUPLING AUDIT ONLY ====="
echo "$OUT"

{
  git grep -n -I -E "from handlers\.generic_schema_flow import SLUG_TO_SECTION|from handlers\.generic_schema_flow import .*SLUG_TO_SECTION|SLUG_TO_SECTION: dict\[str, str\] = \{" -- "*.py" || true
} | sort -u > "$FORBIDDEN"

echo
echo "===== FORBIDDEN MATCHES ====="
cat "$FORBIDDEN"

echo
echo "===== IMPORT SMOKE ====="
venv/bin/python - <<'PY'
from services.catalog_modes import MODE_TO_SECTION_NAME, get_catalog_mode_slugs, get_catalog_section_name

assert isinstance(MODE_TO_SECTION_NAME, dict)
assert len(MODE_TO_SECTION_NAME) >= 30
assert get_catalog_mode_slugs() == set(MODE_TO_SECTION_NAME)
assert get_catalog_section_name("realtors") == MODE_TO_SECTION_NAME["realtors"]
assert get_catalog_section_name("__unknown__") is None
print("catalog_modes_import_smoke_ok", len(MODE_TO_SECTION_NAME))
PY

echo
echo "===== SAFETY CHECKS ====="
if [[ -s "$FORBIDDEN" ]]; then
  echo "ERROR: catalog mode ownership violation detected" >&2
  exit 1
fi
echo "catalog_modes_coupling_audit_ok"

{
  echo "catalog_modes_coupling_audit=$OUT"
  echo
  echo "COUNTS:"
  wc -l "$FORBIDDEN"
  echo
  echo "VERDICT:"
  echo "catalog mode map ownership is centralized in services/catalog_modes.py"
} | tee "$REPORT"

echo
echo "===== OUTPUT ====="
echo "$OUT"
