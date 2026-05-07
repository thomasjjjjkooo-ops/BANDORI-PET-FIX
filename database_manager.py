import sqlite3
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.path.join(BASE_DIR, "data.db")


class DatabaseManager:
    def __init__(self, db_path=DB_PATH):
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def _create_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character TEXT NOT NULL,
                title TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        self._conn.commit()

    def create_conversation(self, character: str, title: str = "") -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self._conn.execute(
            "INSERT INTO conversations (character, title, created_at) VALUES (?, ?, ?)",
            (character, title, now)
        )
        self._conn.commit()
        return cur.lastrowid

    def get_conversations(self, character: str = "") -> list[dict]:
        if character:
            rows = self._conn.execute(
                "SELECT id, character, title, created_at FROM conversations "
                "WHERE character=? AND EXISTS ("
                "SELECT 1 FROM messages WHERE messages.conversation_id=conversations.id"
                ") ORDER BY created_at DESC",
                (character,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, character, title, created_at FROM conversations "
                "WHERE EXISTS ("
                "SELECT 1 FROM messages WHERE messages.conversation_id=conversations.id"
                ") ORDER BY created_at DESC"
            ).fetchall()
        return [
            {"id": r[0], "character": r[1], "title": r[2], "created_at": r[3]}
            for r in rows
        ]

    def get_last_conversation(self, character: str) -> dict | None:
        row = self._conn.execute(
            "SELECT id, character, title, created_at FROM conversations "
            "WHERE character=? AND EXISTS ("
            "SELECT 1 FROM messages WHERE messages.conversation_id=conversations.id"
            ") ORDER BY created_at DESC LIMIT 1",
            (character,)
        ).fetchone()
        if row:
            return {"id": row[0], "character": row[1], "title": row[2], "created_at": row[3]}
        return None

    def update_conversation_title(self, conv_id: int, title: str):
        self._conn.execute(
            "UPDATE conversations SET title=? WHERE id=?",
            (title, conv_id)
        )
        self._conn.commit()

    def add_message(self, conversation_id: int, role: str, content: str) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self._conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, now)
        )
        self._conn.commit()
        return cur.lastrowid

    def get_messages(self, conversation_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, conversation_id, role, content, created_at FROM messages "
            "WHERE conversation_id=? ORDER BY id ASC",
            (conversation_id,)
        ).fetchall()
        return [
            {"id": r[0], "conversation_id": r[1], "role": r[2],
             "content": r[3], "created_at": r[4]}
            for r in rows
        ]

    def delete_conversation(self, conv_id: int):
        self._conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
        self._conn.commit()

    def delete_empty_conversations(self, character: str = ""):
        if character:
            self._conn.execute(
                "DELETE FROM conversations WHERE character=? AND NOT EXISTS ("
                "SELECT 1 FROM messages WHERE messages.conversation_id=conversations.id"
                ")",
                (character,),
            )
        else:
            self._conn.execute(
                "DELETE FROM conversations WHERE NOT EXISTS ("
                "SELECT 1 FROM messages WHERE messages.conversation_id=conversations.id"
                ")"
            )
        self._conn.commit()

    def close(self):
        self._conn.close()
