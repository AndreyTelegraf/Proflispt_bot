#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%dT%H%M%SZ)"
OUT="data/diagnostics/refactor_safety_snapshot_${STAMP}"
mkdir -p "$OUT"

MANIFEST="$OUT/manifest_tracked_source.txt"
GIT_STATUS="$OUT/git_status.txt"
HEAD_FILE="$OUT/head.txt"
SNAPSHOT="$OUT/tracked_source_snapshot_${STAMP}.tar.gz"

echo "===== REFACTOR SAFETY SNAPSHOT ====="
echo "$OUT"

echo
echo "===== HEAD ====="
git rev-parse --short HEAD | tee "$HEAD_FILE"

echo
echo "===== STATUS ====="
git status -sb | tee "$GIT_STATUS"

echo
echo "===== MANIFEST TRACKED SOURCE ONLY ====="
git ls-files \
  "*.py" "*.json" "*.md" "*.sh" "*.service" \
  | grep -vE "^(venv/|data/|opt/|__pycache__/|.*__pycache__/|.*\.pyc$|.*\.pyo$|\.env)" \
  | sort -u \
  | tee "$MANIFEST"

echo
echo "===== VERIFY EXCLUSIONS ====="
if grep -qE "^(venv/|data/|opt/|\.env)" "$MANIFEST"; then
  echo "ERROR: excluded path detected" >&2
  exit 1
fi
echo "tracked_source_manifest_ok"

echo
echo "===== CREATE TRACKED SOURCE SNAPSHOT ====="
tar -czf "$SNAPSHOT" -T "$MANIFEST"

ls -lh "$SNAPSHOT"

echo
echo "===== OUTPUT ====="
echo "$OUT"
