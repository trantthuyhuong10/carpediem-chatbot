import sqlite3
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class MemoryStore:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join("data", "carpediem_chat.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    turn_number INTEGER DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_messages_turn ON messages(session_id, turn_number);
                CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at);
            """)

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        with self.conn:
            self.conn.execute(
                "INSERT INTO sessions (id, created_at, updated_at, message_count) VALUES (?, ?, ?, 0)",
                (session_id, datetime.now().isoformat(), datetime.now().isoformat())
            )
        return session_id

    def load_or_create_session(self) -> str:
        row = self.conn.execute(
            "SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if row:
            return row["id"]
        return self.create_session()

    def save_turn(self, session_id: str, user_msg: str, assistant_msg: str, turn_number: int):
        now = datetime.now().isoformat()
        with self.conn:
            self.conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at, turn_number) VALUES (?, ?, ?, ?, ?)",
                (session_id, "user", user_msg, now, turn_number)
            )
            self.conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at, turn_number) VALUES (?, ?, ?, ?, ?)",
                (session_id, "assistant", assistant_msg, now, turn_number)
            )
            self.conn.execute(
                "UPDATE sessions SET updated_at = ?, message_count = message_count + 2 WHERE id = ?",
                (now, session_id)
            )

    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        rows = self.conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY turn_number DESC, CASE WHEN role = 'user' THEN 0 ELSE 1 END DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        messages = [{"role": r["role"], "content": r["content"]} for r in rows]
        messages.reverse()
        return messages

    def get_session_stats(self, session_id: str) -> Optional[Dict]:
        row = self.conn.execute(
            "SELECT id, created_at, updated_at, message_count FROM sessions WHERE id = ?",
            (session_id,)
        ).fetchone()
        if row:
            return {
                "session_id": row["id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "message_count": row["message_count"],
            }
        return None

    def list_recent_sessions(self, limit: int = 10) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT id, created_at, updated_at, message_count FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: str):
        with self.conn:
            self.conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def cleanup_old_sessions(self, days: int = 30):
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self.conn:
            old_sessions = self.conn.execute(
                "SELECT id FROM sessions WHERE updated_at < ?", (cutoff,)
            ).fetchall()
            for row in old_sessions:
                self.conn.execute("DELETE FROM messages WHERE session_id = ?", (row["id"],))
            self.conn.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))

    def close(self):
        if self.conn:
            self.conn.close()
