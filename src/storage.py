"""Persistencia local en SQLite para suscripciones por canal, pausa y deduplicación."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite

from src.models import ChatTarget, Priority, Subscription


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class BotStorage:
    """Almacenamiento async en SQLite para el estado independiente del bot."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Abre la conexión y crea el esquema SQLite si no existe."""
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")

        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL DEFAULT 0,
                title TEXT,
                is_paused INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (chat_id, thread_id)
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                chat_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL DEFAULT 0,
                source_type TEXT NOT NULL,
                min_priority TEXT NOT NULL,
                min_priority_weight INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (chat_id, thread_id, source_type),
                FOREIGN KEY (chat_id, thread_id)
                    REFERENCES chats(chat_id, thread_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dispatched_items (
                chat_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL DEFAULT 0,
                item_id INTEGER NOT NULL,
                dispatched_at TEXT NOT NULL,
                PRIMARY KEY (chat_id, thread_id, item_id)
            );

            CREATE INDEX IF NOT EXISTS idx_dispatched_at
                ON dispatched_items (dispatched_at);
            """
        )
        await self._conn.commit()

    async def close(self) -> None:
        """Cierra la conexión SQLite abierta."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    def _db(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("BotStorage no inicializado; llama antes a initialize().")
        return self._conn

    async def _ensure_chat(
        self,
        chat_id: int,
        thread_id: int = 0,
        title: str | None = None,
    ) -> None:
        now = _utc_now_iso()
        await self._db().execute(
            """
            INSERT INTO chats (chat_id, thread_id, title, is_paused, created_at, updated_at)
            VALUES (?, ?, ?, 0, ?, ?)
            ON CONFLICT(chat_id, thread_id) DO UPDATE SET
                title = COALESCE(excluded.title, chats.title),
                updated_at = excluded.updated_at
            """,
            (chat_id, thread_id, title, now, now),
        )

    async def subscribe(
        self,
        chat_id: int,
        thread_id: int,
        source_type: str,
        min_priority: Priority,
        title: str | None = None,
    ) -> None:
        """Crea o actualiza una suscripción para el canal/topic."""
        normalized_type = source_type.strip().lower()
        now = _utc_now_iso()
        await self._ensure_chat(chat_id, thread_id, title)
        await self._db().execute(
            """
            INSERT INTO subscriptions (
                chat_id, thread_id, source_type, min_priority, min_priority_weight, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, thread_id, source_type) DO UPDATE SET
                min_priority = excluded.min_priority,
                min_priority_weight = excluded.min_priority_weight
            """,
            (chat_id, thread_id, normalized_type, min_priority.value, min_priority.weight, now),
        )
        await self._db().commit()

    async def unsubscribe(self, chat_id: int, thread_id: int, source_type: str) -> int:
        """Elimina una suscripción específica o todas si source_type == 'all'."""
        normalized_type = source_type.strip().lower()
        if normalized_type == "all":
            cursor = await self._db().execute(
                "DELETE FROM subscriptions WHERE chat_id = ? AND thread_id = ?",
                (chat_id, thread_id),
            )
        else:
            cursor = await self._db().execute(
                """
                DELETE FROM subscriptions
                WHERE chat_id = ? AND thread_id = ? AND source_type = ?
                """,
                (chat_id, thread_id, normalized_type),
            )
        await self._db().commit()
        return cursor.rowcount

    async def list_subscriptions(self, chat_id: int, thread_id: int) -> list[Subscription]:
        """Lista las suscripciones configuradas en un chat/topic."""
        cursor = await self._db().execute(
            """
            SELECT chat_id, thread_id, source_type, min_priority, min_priority_weight
            FROM subscriptions
            WHERE chat_id = ? AND thread_id = ?
            ORDER BY CASE WHEN source_type = 'all' THEN 0 ELSE 1 END, source_type ASC
            """,
            (chat_id, thread_id),
        )
        rows = await cursor.fetchall()
        result: list[Subscription] = []
        for row in rows:
            priority = Priority.parse(str(row["min_priority"])) or Priority.LOW
            result.append(
                Subscription(
                    chat_id=int(row["chat_id"]),
                    thread_id=int(row["thread_id"]),
                    source_type=str(row["source_type"]),
                    min_priority=priority,
                    min_priority_weight=int(row["min_priority_weight"]),
                )
            )
        return result

    async def set_paused(
        self,
        chat_id: int,
        thread_id: int,
        paused: bool,
        title: str | None = None,
    ) -> None:
        """Pausa o reanuda el envío automático de alertas para el chat/topic."""
        await self._ensure_chat(chat_id, thread_id, title)
        await self._db().execute(
            """
            UPDATE chats
            SET is_paused = ?, updated_at = ?
            WHERE chat_id = ? AND thread_id = ?
            """,
            (1 if paused else 0, _utc_now_iso(), chat_id, thread_id),
        )
        await self._db().commit()

    async def is_paused(self, chat_id: int, thread_id: int) -> bool:
        """Indica si el chat/topic tiene pausadas las alertas automáticas."""
        cursor = await self._db().execute(
            "SELECT is_paused FROM chats WHERE chat_id = ? AND thread_id = ?",
            (chat_id, thread_id),
        )
        row = await cursor.fetchone()
        return bool(row["is_paused"]) if row is not None else False

    async def get_matching_targets(self, item_type: str, priority_weight: int) -> list[ChatTarget]:
        """Devuelve destinos activos (no pausados) cuya suscripción coincide sin duplicados."""
        normalized_type = item_type.strip().lower()
        cursor = await self._db().execute(
            """
            SELECT DISTINCT s.chat_id, s.thread_id
            FROM subscriptions s
            INNER JOIN chats c
                ON c.chat_id = s.chat_id AND c.thread_id = s.thread_id
            WHERE c.is_paused = 0
              AND s.min_priority_weight <= ?
              AND s.source_type IN (?, 'all')
            ORDER BY s.chat_id ASC, s.thread_id ASC
            """,
            (priority_weight, normalized_type),
        )
        rows = await cursor.fetchall()
        return [
            ChatTarget(chat_id=int(row["chat_id"]), thread_id=int(row["thread_id"])) for row in rows
        ]

    async def was_dispatched(self, chat_id: int, thread_id: int, item_id: int) -> bool:
        """Comprueba si una noticia ya fue enviada al destino."""
        cursor = await self._db().execute(
            """
            SELECT 1 FROM dispatched_items
            WHERE chat_id = ? AND thread_id = ? AND item_id = ?
            LIMIT 1
            """,
            (chat_id, thread_id, item_id),
        )
        return await cursor.fetchone() is not None

    async def mark_dispatched(self, chat_id: int, thread_id: int, item_id: int) -> None:
        """Registra una noticia como enviada al destino."""
        await self._db().execute(
            """
            INSERT OR IGNORE INTO dispatched_items (chat_id, thread_id, item_id, dispatched_at)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, thread_id, item_id, _utc_now_iso()),
        )
        await self._db().commit()

    async def prune_dispatched(self, retention_days: int = 30) -> int:
        """Elimina registros de deduplicación más antiguos que `retention_days` días."""
        cutoff = (datetime.now(UTC) - timedelta(days=max(0, retention_days))).isoformat()
        cursor = await self._db().execute(
            "DELETE FROM dispatched_items WHERE dispatched_at < ?",
            (cutoff,),
        )
        await self._db().commit()
        return cursor.rowcount

    async def get_last_item_id(self) -> int | None:
        """Lee el último ID de noticia procesado en tiempo real/catch-up."""
        cursor = await self._db().execute(
            "SELECT value FROM bot_state WHERE key = 'last_processed_item_id'"
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        try:
            return int(row["value"])
        except ValueError:
            return None

    async def set_last_item_id(self, item_id: int) -> None:
        """Actualiza el cursor de último ID procesado (solo avanza si es mayor)."""
        current = await self.get_last_item_id()
        if current is not None and item_id <= current:
            return
        await self._db().execute(
            """
            INSERT INTO bot_state (key, value)
            VALUES ('last_processed_item_id', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(item_id),),
        )
        await self._db().commit()

    async def migrate_chat_id(self, old_chat_id: int, new_chat_id: int) -> None:
        """Migra chats, suscripciones e historial de envíos tras un cambio a supergrupo."""
        if old_chat_id == new_chat_id:
            return

        db = self._db()
        cursor = await db.execute(
            """
            SELECT thread_id, title, is_paused, created_at, updated_at
            FROM chats
            WHERE chat_id = ?
            """,
            (old_chat_id,),
        )
        chat_rows = await cursor.fetchall()
        now = _utc_now_iso()

        for row in chat_rows:
            await db.execute(
                """
                INSERT INTO chats (chat_id, thread_id, title, is_paused, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, thread_id) DO UPDATE SET
                    title = COALESCE(excluded.title, chats.title),
                    updated_at = excluded.updated_at
                """,
                (
                    new_chat_id,
                    int(row["thread_id"]),
                    row["title"],
                    int(row["is_paused"]),
                    str(row["created_at"]),
                    now,
                ),
            )

        await db.execute(
            """
            INSERT OR REPLACE INTO subscriptions (
                chat_id, thread_id, source_type, min_priority, min_priority_weight, created_at
            )
            SELECT ?, thread_id, source_type, min_priority, min_priority_weight, created_at
            FROM subscriptions
            WHERE chat_id = ?
            """,
            (new_chat_id, old_chat_id),
        )

        await db.execute(
            """
            INSERT OR IGNORE INTO dispatched_items (chat_id, thread_id, item_id, dispatched_at)
            SELECT ?, thread_id, item_id, dispatched_at
            FROM dispatched_items
            WHERE chat_id = ?
            """,
            (new_chat_id, old_chat_id),
        )

        await db.execute("DELETE FROM dispatched_items WHERE chat_id = ?", (old_chat_id,))
        await db.execute("DELETE FROM chats WHERE chat_id = ?", (old_chat_id,))
        await db.commit()
