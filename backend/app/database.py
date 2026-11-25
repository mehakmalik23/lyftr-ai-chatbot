import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from .config import settings

def get_connection():
    db_path = settings.sqlite_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_configs (
                session_id TEXT PRIMARY KEY,
                system_prompt TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
    conn.close()

def check_db_health() -> bool:
    try:
        conn = get_connection()
        conn.execute("SELECT 1;")
        conn.close()
        return True
    except Exception:
        return False

def get_or_update_system_prompt(session_id: str, new_prompt: str | None) -> str:
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    try:
        if new_prompt is not None and new_prompt.strip():
            prompt = new_prompt.strip()
            with conn:
                conn.execute(
                    "INSERT INTO session_configs (session_id, system_prompt, updated_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(session_id) DO UPDATE SET system_prompt = excluded.system_prompt, updated_at = excluded.updated_at",
                    (session_id, prompt, now)
                )
            return prompt
        row = conn.execute("SELECT system_prompt FROM session_configs WHERE session_id = ?", (session_id,)).fetchone()
        return row["system_prompt"] if row else settings.default_system_prompt
    finally:
        conn.close()

def get_session_messages(session_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT role, content, metadata FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        result = []
        for r in rows:
            item = {"role": r["role"], "content": r["content"]}
            if r["role"] == "assistant" and r["metadata"]:
                full_meta = json.loads(r["metadata"])
                item["metadata"] = {
                    "resolution_source": full_meta.get("resolution_source"),
                    "input_tokens": full_meta.get("input_tokens"),
                    "output_tokens": full_meta.get("output_tokens")
                }
            result.append(item)
        return result
    finally:
        conn.close()

def save_turn(session_id: str, user_message: str, assistant_reply: str, metadata: dict):
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, metadata, created_at) VALUES (?, 'user', ?, NULL, ?)",
                (session_id, user_message, now)
            )
            conn.execute(
                "INSERT INTO messages (session_id, role, content, metadata, created_at) VALUES (?, 'assistant', ?, ?, ?)",
                (session_id, assistant_reply, json.dumps(metadata), now)
            )
    finally:
        conn.close()
