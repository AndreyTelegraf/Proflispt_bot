#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_cleanup_classifier_${STAMP}"

mkdir -p "$OUT"

echo "===== SAFE RUNTIME GARBAGE ====="

find . \
  -path "./venv" -prune -o \
  -type f \
  \( \
    -name "*.pyc" \
    -o -name "*.pyo" \
    -o -name "bot.log" \
    -o -name "*.sqlite" \
  \) \
  -print \
  | sort \
  | tee "$OUT/runtime_garbage.txt"

echo
echo "===== EMPTY DATABASE FILES ====="

find . -type f \
  \( -name "*.db" -o -name "*.sqlite" \) \
  -size 0 \
  | sort \
  | tee "$OUT/empty_databases.txt"

echo
echo "===== HISTORICAL BACKUPS ====="

find . -type f \
  \( \
    -name "*.bak" \
    -o -name "*.bak_*" \
    -o -name "*.pre_*.bak" \
  \) \
  | sort \
  | tee "$OUT/historical_backups.txt"

echo
echo "===== PROTECTED DIAGNOSTICS ====="

find data/diagnostics \
  -maxdepth 1 \
  -mindepth 1 \
  -type d \
  | grep -E \
    "(anchor|audit|review_index|premium|restaurants_e2e)" \
  | sort \
  | tee "$OUT/protected_diagnostics.txt"

echo
echo "===== OUTPUT ====="
echo "$OUT" | tee "$OUT/location.txt"
