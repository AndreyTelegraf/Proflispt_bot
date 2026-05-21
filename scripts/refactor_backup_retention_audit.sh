#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_backup_retention_${STAMP}"
mkdir -p "$OUT"

ALL="$OUT/all_backup_like.txt"
PROTECTED="$OUT/protected_retention.txt"
REVIEW="$OUT/review_required.txt"
LOW="$OUT/low_confidence_cleanup_candidates.txt"

find . \
  -path "./venv" -prune -o \
  -path "./data/diagnostics" -prune -o \
  -type f \
  \( \
    -iname "*.bak" \
    -o -iname "*.bak_*" \
    -o -iname "*.pre_*.bak" \
    -o -iname "*backup*.tar.gz" \
  \) \
  -print \
  | sort -u > "$ALL"

{
  grep -E "pre_residency|pre_review_index|pre_free_repost_guard|deleted_paid_repost|premium|review_index|restaurants_e2e|anchor" "$ALL" || true
  grep -E "^./data/backups_" "$ALL" || true
} | sort -u > "$PROTECTED"

{
  grep -E "database\.py|main\.py|handlers/|services/|config/fsm_schemas/|^./bot_backup.tar.gz" "$ALL" || true
} | sort -u > "$REVIEW"

comm -23 "$ALL" "$PROTECTED" \
  | grep -v -F -f "$REVIEW" \
  | sort -u > "$LOW" || true

echo "===== BACKUP RETENTION AUDIT ONLY ====="
echo "$OUT"

echo
echo "===== ALL BACKUP-LIKE FILES ====="
cat "$ALL"

echo
echo "===== PROTECTED RETENTION ====="
cat "$PROTECTED"

echo
echo "===== REVIEW REQUIRED ====="
cat "$REVIEW"

echo
echo "===== LOW CONFIDENCE CLEANUP CANDIDATES - NOT FOR DELETION YET ====="
cat "$LOW"

echo
echo "===== VERIFY NO VENV / DIAGNOSTICS ====="
if grep -qE "^./venv/|^./data/diagnostics/" "$ALL" "$PROTECTED" "$REVIEW" "$LOW"; then
  echo "ERROR: protected path detected" >&2
  exit 1
fi
echo "protected_paths_ok"

echo
echo "===== COUNTS ====="
wc -l "$ALL" "$PROTECTED" "$REVIEW" "$LOW"
