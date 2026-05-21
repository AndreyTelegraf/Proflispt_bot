#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_diagnostics_preservation_${STAMP}"
mkdir -p "$OUT"

ALL="$OUT/all_diagnostics_dirs.txt"
PROTECTED="$OUT/protected_diagnostics.txt"
REVIEW="$OUT/review_required_diagnostics.txt"
LOW="$OUT/low_confidence_cleanup_candidates.txt"

find data/diagnostics \
  -maxdepth 1 \
  -mindepth 1 \
  -type d \
  | sort -u > "$ALL"

{
  grep -E "restaurants.*anchor|restaurants_e2e|premium|review_index|refactor_audit|rollback|audit" "$ALL" || true
} | sort -u > "$PROTECTED"

{
  cat "$ALL"
} | sort -u > "$REVIEW"

comm -23 "$ALL" "$PROTECTED" \
  | grep -v -F -f "$REVIEW" \
  | sort -u > "$LOW" || true

echo "===== DIAGNOSTICS PRESERVATION AUDIT ONLY ====="
echo "$OUT"

echo
echo "===== ALL DIAGNOSTICS DIRS ====="
cat "$ALL"

echo
echo "===== PROTECTED DIAGNOSTICS ====="
cat "$PROTECTED"

echo
echo "===== REVIEW REQUIRED DIAGNOSTICS ====="
cat "$REVIEW"

echo
echo "===== LOW CONFIDENCE CLEANUP CANDIDATES - NOT FOR DELETION YET ====="
cat "$LOW"

echo
echo "===== VERIFY ONLY DIAGNOSTICS PATHS ====="
if grep -vE "^data/diagnostics/" "$ALL" "$PROTECTED" "$REVIEW" "$LOW" | grep -q .; then
  echo "ERROR: non-diagnostics path detected" >&2
  exit 1
fi
echo "diagnostics_paths_ok"

echo
echo "===== COUNTS ====="
wc -l "$ALL" "$PROTECTED" "$REVIEW" "$LOW"
