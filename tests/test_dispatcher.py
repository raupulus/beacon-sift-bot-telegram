"""Tests unitarios para AlertDispatcher (filtrado, topics, deduplicación y Forbidden)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from telegram.error import ChatMigrated, Forbidden, RetryAfter, TelegramError

from src.config import Settings
from src.dispatcher import AlertDispatcher
from src.models import NewsItem, Priority, SourceSummary
from src.storage import BotStorage


class FakeBot:
    def __init__(
        self,
        forbidden_chats: set[int] | None = None,
        migrated_chats: dict[int, int] | None = None,
        retry_once_chats: set[int] | None = None,
        always_retry_chats: set[int] | None = None,
    ) -> None:
        self.sent: list[dict[str, Any]] = []
        self.forbidden_chats = forbidden_chats or set()
        self.migrated_chats = migrated_chats or {}
        self.retry_once_chats = set(retry_once_chats or set())
        self.always_retry_chats = set(always_retry_chats or set())

    async def send_message(self, **kwargs: Any) -> None:
        chat_id = int(kwargs["chat_id"])
        if chat_id in self.migrated_chats:
            raise ChatMigrated(self.migrated_chats[chat_id])
        if chat_id in self.retry_once_chats:
            self.retry_once_chats.remove(chat_id)
            raise RetryAfter(0.01)
        if chat_id in self.always_retry_chats:
            raise RetryAfter(0.01)
        if chat_id in self.forbidden_chats:
            raise Forbidden("Bot was kicked")
        self.sent.append(kwargs)


def _make_item(
    item_id: int, item_type: str = "cve", priority: Priority = Priority.HIGH
) -> NewsItem:
    return NewsItem(
        id=item_id,
        title=f"Alert #{item_id}",
        url=f"https://example.org/{item_id}",
        type=item_type,
        priority=priority,
        priority_weight=priority.weight,
        published_at=datetime(2026, 11, 20, 14, 0, tzinfo=UTC),
        fetched_at=datetime(2026, 11, 20, 14, 1, tzinfo=UTC),
        snippet="Detalle breve",
        source=SourceSummary(slug="debian", name="Debian", url="https://debian.org"),
    )


async def test_dispatcher_delivers_with_thread_id_dedups_and_pauses_on_forbidden(
    tmp_path: Path,
) -> None:
    storage = BotStorage(tmp_path / "bot.db")
    await storage.initialize()
    try:
        await storage.subscribe(-1001, 42, "cve", Priority.MEDIUM)
        await storage.subscribe(-1002, 0, "cve", Priority.CRITICAL)  # no cumple HIGH
        await storage.subscribe(-1003, 0, "all", Priority.LOW)  # expulsado -> Forbidden

        bot = FakeBot(forbidden_chats={-1003})
        settings = Settings(telegram_disable_web_preview=True)
        dispatcher = AlertDispatcher(bot, storage, settings)

        delivered = await dispatcher.dispatch_item(_make_item(77, "cve", Priority.HIGH))
        assert delivered == 1
        assert len(bot.sent) == 1
        assert bot.sent[0]["chat_id"] == -1001
        assert bot.sent[0]["message_thread_id"] == 42
        assert bot.sent[0]["link_preview_options"].is_disabled is True

        # Chat -1003 quedó pausado automáticamente tras Forbidden
        assert await storage.is_paused(-1003, 0) is True

        # Reenvío del mismo item -> deduplicado, 0 envíos
        delivered_again = await dispatcher.dispatch_item(_make_item(77, "cve", Priority.HIGH))
        assert delivered_again == 0
    finally:
        await storage.close()


async def test_dispatcher_handles_retry_after_and_dynamic_types_per_chat(tmp_path: Path) -> None:
    storage = BotStorage(tmp_path / "bot.db")
    await storage.initialize()
    try:
        # Cada grupo tiene tipos dinámicos propios (p. ej. 'iot' creado en web/)
        await storage.subscribe(-2001, 0, "iot", Priority.LOW)
        await storage.subscribe(-2002, 0, "cve", Priority.LOW)
        await storage.subscribe(-2003, 0, "all", Priority.MEDIUM)

        bot = FakeBot(retry_once_chats={-2001}, always_retry_chats={-2003})
        dispatcher = AlertDispatcher(
            bot, storage, Settings(), max_concurrency=4, min_interval_seconds=0.0
        )

        delivered = await dispatcher.dispatch_item(_make_item(101, "iot", Priority.MEDIUM))
        assert delivered == 1
        assert [m["chat_id"] for m in bot.sent] == [-2001]
        assert await storage.was_dispatched(-2001, 0, 101) is True
        assert await storage.was_dispatched(-2002, 0, 101) is False
        assert await storage.was_dispatched(-2003, 0, 101) is False
    finally:
        await storage.close()


async def test_dispatcher_migrates_chat_id_and_prunes_periodically(tmp_path: Path) -> None:
    storage = BotStorage(tmp_path / "bot.db")
    await storage.initialize()
    try:
        await storage.subscribe(-300, 0, "linux", Priority.LOW)
        await storage.mark_dispatched(-999, 0, 1)
        await storage._db().execute(
            "UPDATE dispatched_items SET dispatched_at = ? WHERE chat_id = ?",
            ("2020-01-01T00:00:00+00:00", -999),
        )
        await storage._db().commit()

        bot = FakeBot(migrated_chats={-300: -100300})
        dispatcher = AlertDispatcher(
            bot,
            storage,
            Settings(),
            prune_every=2,
            prune_retention_days=30,
            min_interval_seconds=0.0,
        )

        # 1ª entrega: migra -300 -> -100300 y entrega al supergrupo
        assert await dispatcher.dispatch_item(_make_item(1, "linux", Priority.LOW)) == 1
        assert bot.sent[-1]["chat_id"] == -100300
        assert await storage.list_subscriptions(-300, 0) == []
        assert len(await storage.list_subscriptions(-100300, 0)) == 1
        assert await storage.was_dispatched(-100300, 0, 1) is True
        assert await storage.was_dispatched(-999, 0, 1) is True

        # 2ª entrega: ya va directo a -100300 y dispara prune_dispatched(retention_days=30)
        assert await dispatcher.dispatch_item(_make_item(2, "linux", Priority.LOW)) == 1
        assert await storage.was_dispatched(-100300, 0, 2) is True
        assert await storage.was_dispatched(-100300, 0, 1) is True
        assert await storage.was_dispatched(-999, 0, 1) is False
    finally:
        await storage.close()


async def test_dispatcher_logs_generic_telegram_error_without_crashing(tmp_path: Path) -> None:
    class FailingBot:
        async def send_message(self, **kwargs: Any) -> None:
            raise TelegramError("Temporary upstream failure")

    storage = BotStorage(tmp_path / "bot.db")
    await storage.initialize()
    try:
        await storage.subscribe(-400, 0, "all", Priority.LOW)
        dispatcher = AlertDispatcher(FailingBot(), storage, Settings())
        assert await dispatcher.dispatch_item(_make_item(55, "cve", Priority.CRITICAL)) == 0
        assert await storage.was_dispatched(-400, 0, 55) is False
    finally:
        await storage.close()
