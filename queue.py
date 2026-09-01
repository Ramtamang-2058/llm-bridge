"""
Simple local task queue backed by SQLite. Plain JSON/text fields —
no hashing — so you can open tasks.db with any SQLite viewer and
read exactly what happened.
"""
import sqlite3
from datetime import datetime, timezone

DB_PATH = "tasks.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assigned_to TEXT NOT NULL,       -- 'claude' | 'chatgpt' | 'gemini'
            prompt TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',  -- pending | in_progress | done | error
            result TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def add_task(assigned_to: str, prompt: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO tasks (assigned_to, prompt, status, created_at, updated_at) "
        "VALUES (?, ?, 'pending', ?, ?)",
        (assigned_to, prompt, now, now),
    )
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return task_id


def get_next_pending():
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM tasks WHERE status = 'pending' ORDER BY id ASC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_in_progress(task_id: int):
    _update(task_id, status="in_progress")


def mark_done(task_id: int, result: str):
    _update(task_id, status="done", result=result)


def mark_error(task_id: int, error_message: str):
    _update(task_id, status="error", result=error_message)


def _update(task_id: int, status: str, result: str = None):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    conn.execute(
        "UPDATE tasks SET status = ?, result = ?, updated_at = ? WHERE id = ?",
        (status, result, now, task_id),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    import json

    # Quick manual test: `python queue.py` seeds one task per service.
    init_db()
    add_task("gemini", "Open the shared tracking sheet and list any rows marked 'pending'.")
    add_task("chatgpt", "Summarize today's open Jira tickets assigned to me in 3 bullet points.")
    print(json.dumps(get_next_pending(), indent=2))
