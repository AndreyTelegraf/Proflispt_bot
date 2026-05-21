#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_final_sanitation_${STAMP}"
mkdir -p "$OUT"

RUNTIME="$OUT/runtime_candidates.txt"
BACKUPS_PROTECTED="$OUT/backup_protected.txt"
BACKUPS_REVIEW="$OUT/backup_review_required.txt"
BACKUPS_LOW="$OUT/backup_low_confidence.txt"
DIAG_PROTECTED="$OUT/diagnostics_protected.txt"
DIAG_REVIEW="$OUT/diagnostics_review_required.txt"
DIAG_LOW="$OUT/diagnostics_low_confidence.txt"
REPORT="$OUT/report.txt"

echo "===== FINAL SANITATION AUDIT ONLY ====="
echo "$OUT"

echo
echo "===== RUN SAFETY SNAPSHOT ====="
scripts/refactor_safety_snapshot.sh | tee "$OUT/safety_snapshot_run.txt"

echo
echo "===== RUNTIME CLEANUP DRY RUN ====="
scripts/refactor_cleanup_runtime_garbage.sh --dry-run | tee "$OUT/runtime_cleanup_dry_run.txt"

latest_runtime_dir="$(grep -E "^data/diagnostics/refactor_runtime_cleanup_" "$OUT/runtime_cleanup_dry_run.txt" | tail -1)"
if [[ -n "$latest_runtime_dir" && -f "$latest_runtime_dir/candidates.txt" ]]; then
  cp "$latest_runtime_dir/candidates.txt" "$RUNTIME"
else
  : > "$RUNTIME"
fi

echo
echo "===== BACKUP RETENTION AUDIT ====="
scripts/refactor_backup_retention_audit.sh | tee "$OUT/backup_retention_run.txt"

latest_backup_dir="$(grep -E "^data/diagnostics/refactor_backup_retention_" "$OUT/backup_retention_run.txt" | tail -1)"
if [[ -n "$latest_backup_dir" ]]; then
  cp "$latest_backup_dir/protected_retention.txt" "$BACKUPS_PROTECTED"
  cp "$latest_backup_dir/review_required.txt" "$BACKUPS_REVIEW"
  cp "$latest_backup_dir/low_confidence_cleanup_candidates.txt" "$BACKUPS_LOW"
else
  : > "$BACKUPS_PROTECTED"; : > "$BACKUPS_REVIEW"; : > "$BACKUPS_LOW"
fi

echo
echo "===== DIAGNOSTICS PRESERVATION AUDIT ====="
scripts/refactor_diagnostics_preservation_audit.sh | tee "$OUT/diagnostics_preservation_run.txt"

latest_diag_dir="$(grep -E "^data/diagnostics/refactor_diagnostics_preservation_" "$OUT/diagnostics_preservation_run.txt" | tail -1)"
if [[ -n "$latest_diag_dir" ]]; then
  cp "$latest_diag_dir/protected_diagnostics.txt" "$DIAG_PROTECTED"
  cp "$latest_diag_dir/review_required_diagnostics.txt" "$DIAG_REVIEW"
  cp "$latest_diag_dir/low_confidence_cleanup_candidates.txt" "$DIAG_LOW"
else
  : > "$DIAG_PROTECTED"; : > "$DIAG_REVIEW"; : > "$DIAG_LOW"
fi

echo
echo "===== SAFETY CHECKS ====="
if grep -qE "^./venv/|^venv/" "$RUNTIME" "$BACKUPS_PROTECTED" "$BACKUPS_REVIEW" "$BACKUPS_LOW" "$DIAG_PROTECTED" "$DIAG_REVIEW" "$DIAG_LOW"; then
  echo "ERROR: venv path detected" >&2
  exit 1
fi

if [[ -s "$BACKUPS_LOW" ]]; then
  echo "ERROR: backup low-confidence cleanup candidates are non-empty; destructive cleanup blocked" >&2
  exit 1
fi

if [[ -s "$DIAG_LOW" ]]; then
  echo "ERROR: diagnostics low-confidence cleanup candidates are non-empty; destructive cleanup blocked" >&2
  exit 1
fi

if grep -F -x -f "$BACKUPS_PROTECTED" "$BACKUPS_LOW" | grep -q .; then
  echo "ERROR: backup protected intersects cleanup candidates" >&2
  exit 1
fi

if grep -F -x -f "$DIAG_PROTECTED" "$DIAG_LOW" | grep -q .; then
  echo "ERROR: diagnostics protected intersects cleanup candidates" >&2
  exit 1
fi

echo "safety_checks_ok"

{
  echo "final_sanitation_audit=$OUT"
  echo
  echo "HEAD:"
  git rev-parse --short HEAD
  echo
  echo "STATUS:"
  git status -sb
  echo
  echo "COUNTS:"
  wc -l "$RUNTIME" "$BACKUPS_PROTECTED" "$BACKUPS_REVIEW" "$BACKUPS_LOW" "$DIAG_PROTECTED" "$DIAG_REVIEW" "$DIAG_LOW"
  echo
  echo "VERDICT:"
  echo "runtime cleanup may proceed via scripts/refactor_cleanup_runtime_garbage.sh --apply"
  echo "backup destructive cleanup blocked: no approved deletion set yet"
  echo "diagnostics destructive cleanup blocked: no approved deletion set yet"
} | tee "$REPORT"

echo
echo "===== OUTPUT ====="
echo "$OUT"
