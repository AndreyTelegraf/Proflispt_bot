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
"$PY" - <<'PY'
import sqlite3
from pathlib import Path

db = Path("bot_database.db")
print("DB_EXISTS", db.exists())
if db.exists():
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print("TABLES", ",".join(tables))
    for t in ["users", "job_postings", "drafts", "user_bans", "premium_posts", "payments"]:
        try:
            n = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            print(f"COUNT {t} {n}")
        except Exception as e:
            print(f"COUNT_ERROR {t} {e}")
    conn.close()
PY
echo "HEALTHCHECK_OK"
