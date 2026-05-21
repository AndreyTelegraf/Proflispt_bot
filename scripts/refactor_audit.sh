#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_audit_${STAMP}"

mkdir -p "$OUT"

echo "===== HEAD ====="
git rev-parse --short HEAD | tee "$OUT/head.txt"

echo
echo "===== STATUS ====="
git status --short | tee "$OUT/git_status.txt"

echo
echo "===== UNTRACKED ====="
git ls-files --others --exclude-standard | tee "$OUT/untracked.txt"

echo
echo "===== COMPILE ====="
venv/bin/python -m py_compile \
  main.py \
  database.py \
  handlers/generic_schema_flow.py \
  handlers/housing_schema_flow.py \
  handlers/restaurants_schema.py \
  services/listing_validation.py \
  2>&1 | tee "$OUT/compile.txt"

echo
echo "===== SERVICE ====="
systemctl is-active proflistpt_bot_refactor.service \
  | tee "$OUT/service_status.txt"

echo
echo "===== JOURNAL ====="
journalctl -u proflistpt_bot_refactor.service \
  -n 80 \
  --no-pager \
  | tee "$OUT/journal_tail.txt"

echo
echo "===== DATABASE FILES ====="
find . -maxdepth 3 -type f \
  \( -name "*.db" -o -name "*.sqlite" \) \
  -printf "%p\t%s bytes\t%TY-%Tm-%Td %TH:%TM\n" \
  | sort \
  | tee "$OUT/database_files.txt"

echo
echo "===== LARGE FILES ====="
find . -type f -printf "%s\t%p\n" \
  | sort -nr \
  | sed -n "1,40p" \
  | tee "$OUT/large_files.txt"

echo
echo "===== AUDIT OUTPUT ====="
echo "$OUT" | tee "$OUT/location.txt"
