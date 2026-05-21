#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_python_legacy_docstrings_${STAMP}"
mkdir -p "$OUT"

MATCHES="$OUT/legacy_python_matches.txt"
REPORT="$OUT/report.txt"

echo "===== PYTHON LEGACY DOCSTRING AUDIT ONLY ====="
echo "$OUT"

git grep -n -I -E "Work in Portugal Bot|Work in Portugal Telegram Bot" -- "*.py" > "$MATCHES" || true

echo
echo "===== LEGACY PYTHON MATCHES ====="
cat "$MATCHES"

echo
echo "===== SAFETY CHECKS ====="
if [[ -s "$MATCHES" ]]; then
  echo "ERROR: legacy Python bot naming remains" >&2
  exit 1
fi
echo "python_legacy_docstring_audit_ok"

{
  echo "python_legacy_docstring_audit=$OUT"
  echo
  echo "COUNTS:"
  wc -l "$MATCHES"
  echo
  echo "VERDICT:"
  echo "Python source no longer contains legacy Work in Portugal Bot naming"
} | tee "$REPORT"

echo
echo "===== OUTPUT ====="
echo "$OUT"
