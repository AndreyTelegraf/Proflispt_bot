#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${1:---dry-run}"

if [[ "$MODE" != "--dry-run" && "$MODE" != "--apply" ]]; then
  echo "Usage: scripts/refactor_cleanup_runtime_garbage.sh [--dry-run|--apply]" >&2
  exit 2
fi

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_runtime_cleanup_${STAMP}"
mkdir -p "$OUT"

CANDIDATES="$OUT/candidates.txt"

{
  find . \
    -path "./venv" -prune -o \
    -type f \
    \( -name "*.pyc" -o -name "*.pyo" -o -name "bot.log" \) \
    -print

  find ./data \
    -type f \
    \( -name "*.db" -o -name "*.sqlite" \) \
    -size 0 \
    -print 2>/dev/null || true
} | sort -u > "$CANDIDATES"

echo "===== MODE ====="
echo "$MODE"

echo
echo "===== CANDIDATES ====="
cat "$CANDIDATES"

echo
echo "===== VERIFY NO VENV ====="
if grep -q '^./venv/' "$CANDIDATES"; then
  echo "ERROR: venv candidate detected" >&2
  exit 1
fi
echo "no_venv_ok"

if [[ "$MODE" == "--apply" ]]; then
  echo
  echo "===== DELETE ====="
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    rm -f -- "$path"
    echo "deleted $path"
  done < "$CANDIDATES"

  echo
  echo "===== DELETE EMPTY __PYCACHE__ DIRS ====="
  find . \
    -type d \
    -name "__pycache__" \
    -not -path "./venv/*" \
    -empty \
    -print \
    -exec rmdir {} +
else
  echo
  echo "===== DRY RUN ONLY ====="
fi

echo
echo "===== OUTPUT ====="
echo "$OUT"
