#!/usr/bin/env bash
set -euo pipefail

if [ -x "venv/bin/python" ]; then
  PY="venv/bin/python"
elif [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  echo "ERROR: no project python found"
  exit 1
fi

"$PY" -m py_compile main.py config.py database.py handlers/*.py services/*.py middleware/*.py keyboards/*.py models/*.py
echo "PY_COMPILE_OK"
