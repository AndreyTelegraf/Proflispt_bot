#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_renderer_coupling_${STAMP}"
mkdir -p "$OUT"

MATCHES="$OUT/matches.txt"
REPORT="$OUT/report.txt"

echo "===== RENDERER COUPLING AUDIT ONLY ====="
echo "$OUT"

{
  git grep -n -I -E "from handlers\.restaurants_schema import _render_html|from handlers\.generic_schema_flow import _render_html|from handlers\.generic_schema_flow import SLUG_TO_SECTION|from handlers\.generic_schema_flow import .*SLUG_TO_SECTION|_render_html as _gs_render_html|_render_html as _restaurants" -- "*.py" || true
} | sort -u > "$MATCHES"

echo
echo "===== FORBIDDEN COUPLING MATCHES ====="
cat "$MATCHES"

echo
echo "===== SAFETY CHECKS ====="
if [[ -s "$MATCHES" ]]; then
  echo "ERROR: forbidden renderer/catalog mode handler coupling detected" >&2
  exit 1
fi
echo "renderer_coupling_audit_ok"

{
  echo "renderer_coupling_audit=$OUT"
  echo
  echo "COUNTS:"
  wc -l "$MATCHES"
  echo
  echo "VERDICT:"
  echo "premium/admin and shared rendering layers are not coupled to handler renderer wrappers"
} | tee "$REPORT"

echo
echo "===== OUTPUT ====="
echo "$OUT"
