"""SQLite-backed memory store for conversation history and user profiling."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


class MemoryStore:
    """Persistent memory store using SQLite (async).

    Stores conversation history per chat and user interaction profiles.
    """

    def __init__(self, db_path: str = "data/userbot.db") -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open database connection and create tables if needed."""
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")

        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT DEFAULT '',
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_messages_chat_ts
                ON messages(chat_id, timestamp DESC);

            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                last_name TEXT DEFAULT '',
                interaction_count INTEGER DEFAULT 0,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS response_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                response TEXT NOT NULL,
                delay_seconds REAL DEFAULT 0,
                timestamp REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_response_log_ts
                ON response_log(timestamp DESC);
        """)
        await self._db.commit()
        logger.info("Memory store initialized at %s", self._db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            logger.info("Memory store closed.")

    async def store_message(
        self,
        chat_id: int,
        user_id: int,
        user_name: str,
        role: str,
        content: str,
    ) -> None:
        """Store a message in conversation history."""
        if not self._db:
            return
        await self._db.execute(
            "INSERT INTO messages (chat_id, user_id, user_name, role, content, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, user_id, user_name, role, content, time.time()),
        )
        await self._db.commit()

    async def get_context(
        self,
        chat_id: int,
        limit: int = 10,
    ) -> list[dict[str, str]]:
        """Retrieve recent messages for a chat as context for the AI.

        Returns messages in chronological order formatted as
        [{"role": "user"|"assistant", "content": "..."}].
        """
        if not self._db:
            return []
        cursor = await self._db.execute(
            "SELECT role, content, user_name FROM messages "
            "WHERE chat_id = ? ORDER BY timestamp DESC LIMIT ?",
            (chat_id, limit),
        )
        rows = await cursor.fetchall()

        # Reverse to chronological order
        messages = []
        for role, content, user_name in reversed(rows):
            if role == "user" and user_name:
                messages.append({"role": role, "content": f"{user_name}: {content}"})
            else:
                messages.append({"role": role, "content": content})
        return messages

    async def update_user_profile(
        self,
        user_id: int,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
    ) -> None:
        """Update or create a user profile entry."""
        if not self._db:
            return
        now = time.time()
        await self._db.execute(
            """INSERT INTO user_profiles (user_id, username, first_name, last_name,
                interaction_count, first_seen, last_seen)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                interaction_count = interaction_count + 1,
                last_seen = excluded.last_seen
            """,
            (user_id, username, first_name, last_name, now, now),
        )
        await self._db.commit()

    async def get_user_profile(self, user_id: int) -> dict | None:
        """Retrieve a user profile."""
        if not self._db:
            return None
        cursor = await self._db.execute(
            "SELECT user_id, username, first_name, last_name, interaction_count, "
            "first_seen, last_seen, metadata FROM user_profiles WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "user_id": row[0],
            "username": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "interaction_count": row[4],
            "first_seen": row[5],
            "last_seen": row[6],
            "metadata": json.loads(row[7]) if row[7] else {},
        }

    async def log_response(
        self,
        chat_id: int,
        user_id: int,
        prompt: str,
        response: str,
        delay_seconds: float = 0,
    ) -> None:
        """Log a response for debugging and analysis."""
        if not self._db:
            return
        await self._db.execute(
            "INSERT INTO response_log (chat_id, user_id, prompt, response, delay_seconds, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, user_id, prompt, response, delay_seconds, time.time()),
        )
        await self._db.commit()

    async def get_frequent_contacts(self, limit: int = 20) -> list[dict]:
        """Get the most frequently interacted-with users."""
        if not self._db:
            return []
        cursor = await self._db.execute(
            "SELECT user_id, username, first_name, last_name, interaction_count, last_seen "
            "FROM user_profiles ORDER BY interaction_count DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "user_id": r[0],
                "username": r[1],
                "first_name": r[2],
                "last_name": r[3],
                "interaction_count": r[4],
                "last_seen": r[5],
            }
            for r in rows
        ]

    async def get_stats(self) -> dict:
        """Get overall statistics from the memory store."""
        if not self._db:
            return {}
        msg_count = await self._db.execute("SELECT COUNT(*) FROM messages")
        user_count = await self._db.execute("SELECT COUNT(*) FROM user_profiles")
        resp_count = await self._db.execute("SELECT COUNT(*) FROM response_log")

        return {
            "total_messages": (await msg_count.fetchone())[0],
            "total_users": (await user_count.fetchone())[0],
            "total_responses": (await resp_count.fetchone())[0],
        }
