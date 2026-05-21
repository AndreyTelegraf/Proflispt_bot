#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_restaurants_artifact_${STAMP}"
mkdir -p "$OUT"

ALL="$OUT/restaurants_all_matches.txt"
RUNTIME="$OUT/runtime_critical.txt"
REAL_SECTION="$OUT/real_restaurants_section.txt"
TEMPLATE_CANDIDATES="$OUT/template_artifact_candidates.txt"
HISTORICAL="$OUT/historical_or_diagnostics.txt"
REPORT="$OUT/report.txt"

echo "===== RESTAURANTS ARTIFACT AUDIT ONLY ====="
echo "$OUT"

git grep -n -I -E "restaurants|Restaurants|restaurant|Restaurant" \
  -- \
  "*.py" "*.json" "*.md" "*.sh" "*.service" \
  > "$ALL" || true

grep -E "^(main\.py|database\.py|handlers/|services/|config/|app/)" "$ALL" \
  | sort -u > "$RUNTIME" || true

grep -E "(section:restaurants|confirm:restaurants_post|restaurants:|config/fsm_schemas/restaurants\.json|restaurants_schema\.py|mode.*restaurants|slug.*restaurants)" "$ALL" \
  | sort -u > "$REAL_SECTION" || true

grep -E "(canonical|template|schema flow|schema_flow|restaurants_schema\.py|handlers/restaurants_schema\.py|_render_html|_choice_keyboard|_step_reply_markup|_start_flow|PostingContext)" "$ALL" \
  | sort -u > "$TEMPLATE_CANDIDATES" || true

grep -E "^(data/diagnostics|data/backups|docs/refactor/)" "$ALL" \
  | sort -u > "$HISTORICAL" || true

echo
echo "===== ALL MATCHES ====="
cat "$ALL"

echo
echo "===== RUNTIME CRITICAL ====="
cat "$RUNTIME"

echo
echo "===== REAL RESTAURANTS SECTION ====="
cat "$REAL_SECTION"

echo
echo "===== TEMPLATE ARTIFACT CANDIDATES ====="
cat "$TEMPLATE_CANDIDATES"

echo
echo "===== HISTORICAL / DIAGNOSTICS ====="
cat "$HISTORICAL"

echo
echo "===== SAFETY CHECKS ====="
if grep -qE "^venv/|^data/diagnostics/.+\\.tar\\.gz" "$ALL"; then
  echo "ERROR: unsafe scanned path detected" >&2
  exit 1
fi
echo "restaurants_artifact_audit_ok"

{
  echo "restaurants_artifact_audit=$OUT"
  echo
  echo "COUNTS:"
  wc -l "$ALL" "$RUNTIME" "$REAL_SECTION" "$TEMPLATE_CANDIDATES" "$HISTORICAL"
  echo
  echo "VERDICT:"
  echo "rename blocked until real section references are separated from reusable flow logic"
  echo "historical diagnostics/backups should not be rewritten"
  echo "first refactor target should be extracting reusable helpers, not renaming callback namespace"
} | tee "$REPORT"

echo
echo "===== OUTPUT ====="
echo "$OUT"
