#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_legacy_naming_${STAMP}"
mkdir -p "$OUT"

ALL="$OUT/workinportugal_all_matches.txt"
RUNTIME="$OUT/runtime_critical.txt"
USER_FACING="$OUT/user_facing_or_docs.txt"
HISTORICAL="$OUT/historical_or_diagnostics.txt"
REVIEW="$OUT/review_required.txt"
REPORT="$OUT/report.txt"

echo "===== LEGACY NAMING AUDIT ONLY ====="
echo "$OUT"

git grep -n -I -E "workinportugal|Work in Portugal|workinportugal_bot|workinportugal-bot|proflispt|Proflispt" \
  -- \
  "*.py" "*.json" "*.md" "*.sh" "*.service" \
  | grep -v "^scripts/refactor_legacy_naming_audit\.sh:" \
  > "$ALL" || true

grep -E "^(data/diagnostics|data/backups|.*\.bak|docs/refactor/)|workinportugal_bot_stable_|telegram_workinportugal_bot\.tar\.gz|^infra_restructure_summary\.md:" "$ALL" \
  | sort -u > "$HISTORICAL" || true

grep -v "^scripts/refactor_legacy_naming_audit\.sh:" "$ALL" \
  | grep -v -F -x -f "$HISTORICAL" \
  | grep -E "^(config\.py|main\.py|database\.py|.*\.service|.*\.sh|handlers/|services/)" \
  | sort -u > "$RUNTIME" || true

grep -v "^scripts/refactor_legacy_naming_audit\.sh:" "$ALL" \
  | grep -v -F -x -f "$HISTORICAL" \
  | grep -E "(\.md:|README|TECHNICAL|CHANGELOG|PREMIUM|ADMIN|BAN|CLEANUP|docs/)" \
  | sort -u > "$USER_FACING" || true

cat "$ALL" | sort -u > "$REVIEW"

echo
echo "===== ALL MATCHES ====="
cat "$ALL"

echo
echo "===== RUNTIME CRITICAL / HIGH RISK ====="
cat "$RUNTIME"

echo
echo "===== USER-FACING OR DOCS ====="
cat "$USER_FACING"

echo
echo "===== HISTORICAL / DIAGNOSTICS ====="
cat "$HISTORICAL"

echo
echo "===== SAFETY CHECKS ====="
if grep -qE "^venv/|^data/diagnostics/.+\.tar\.gz" "$ALL"; then
  echo "ERROR: unsafe scanned path detected" >&2
  exit 1
fi
echo "legacy_naming_audit_ok"

{
  echo "legacy_naming_audit=$OUT"
  echo
  echo "COUNTS:"
  wc -l "$ALL" "$RUNTIME" "$USER_FACING" "$HISTORICAL" "$REVIEW"
  echo
  echo "VERDICT:"
  echo "rename blocked until runtime-critical matches are reviewed one by one"
  echo "historical diagnostics/backups should not be rewritten"
  echo "docs/user-facing strings may be renamed first after review"
} | tee "$REPORT"

echo
echo "===== OUTPUT ====="
echo "$OUT"
