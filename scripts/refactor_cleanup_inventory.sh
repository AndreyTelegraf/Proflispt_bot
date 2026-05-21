#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_cleanup_inventory_${STAMP}"

mkdir -p "$OUT"

echo "===== REFRACTOR CLEANUP INVENTORY ====="

echo
echo "===== BACKUP FILES ====="
find . -type f \
  \( \
    -name "*.bak" \
    -o -name "*.bak_*" \
    -o -name "*.pre_*.bak" \
    -o -name "*.tar.gz" \
  \) \
  | sort \
  | tee "$OUT/backup_files.txt"

echo
echo "===== DATABASE SNAPSHOTS ====="
find . -type f \
  \( \
    -name "*.db" \
    -o -name "*.sqlite" \
  \) \
  | sort \
  | tee "$OUT/database_files.txt"

echo
echo "===== DIAGNOSTICS DIRS ====="
find data/diagnostics \
  -maxdepth 1 \
  -mindepth 1 \
  -type d \
  | sort \
  | tee "$OUT/diagnostics_dirs.txt"

echo
echo "===== TOTAL SIZES ====="
{
  echo "--- backup artifacts ---"
  du -sh \
    $(cat "$OUT/backup_files.txt") 2>/dev/null || true

  echo
  echo "--- database artifacts ---"
  du -sh \
    $(cat "$OUT/database_files.txt") 2>/dev/null || true
} | tee "$OUT/sizes.txt"

echo
echo "===== OUTPUT ====="
echo "$OUT" | tee "$OUT/location.txt"
