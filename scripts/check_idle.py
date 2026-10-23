"""Refuse planned service restarts while any persisted task is active."""
from pathlib import Path
import sqlite3
import sys
path = Path(__file__).resolve().parents[1] / '.local/tasks.sqlite3'
with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
    count = db.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('queued','running','awaiting_approval','paused')").fetchone()[0]
if count:
    print('LocalPilot has active tasks. Finish or cancel them before restarting services.')
    sys.exit(2)
print('No active LocalPilot tasks.')
