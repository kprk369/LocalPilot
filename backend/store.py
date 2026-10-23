"""Durable task summaries and append-only event history."""
import json
import sqlite3
from datetime import datetime, timezone

class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, request TEXT NOT NULL, status TEXT NOT NULL, result TEXT, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL, created TEXT NOT NULL);
        ''')
        self.db.execute("UPDATE tasks SET status='interrupted' WHERE status IN ('queued','running','awaiting_approval','paused')")
        self.db.commit()

    def routine_approval(self):
        row=self.db.execute("SELECT value FROM preferences WHERE key='routine_auto_approve'").fetchone()
        return bool(row and row[0]=='true')

    def set_routine_approval(self,enabled):
        self.db.execute("INSERT OR REPLACE INTO preferences VALUES('routine_auto_approve',?)",('true' if enabled else 'false',))
        self.db.commit()

    def create(self, task_id, request):
        self.db.execute('INSERT INTO tasks VALUES(?,?,?,?,?)', (task_id, request, 'queued', None, datetime.now(timezone.utc).isoformat()))
        self.db.commit()

    def get(self, task_id):
        row = self.db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        return dict(row) if row else None

    def recent(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM tasks ORDER BY created DESC LIMIT 50')]

    def update(self, task_id, status, result=None):
        self.db.execute('UPDATE tasks SET status=?, result=? WHERE id=?', (status, result, task_id))
        self.db.commit()
        self.event(task_id, 'status', {'status': status, 'result': result})

    def event(self, task_id, kind, data):
        self.db.execute('INSERT INTO events(task_id,kind,data,created) VALUES(?,?,?,?)', (task_id, kind, json.dumps(data), datetime.now(timezone.utc).isoformat()))
        self.db.commit()

    def events(self, task_id, after=0):
        rows = self.db.execute('SELECT * FROM events WHERE task_id=? AND id>? ORDER BY id LIMIT 500', (task_id, after))
        return [{**dict(row), 'data': json.loads(row['data'])} for row in rows]
