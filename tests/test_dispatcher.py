"""Tests unitarios para AlertDispatcher (filtrado, topics, deduplicación y Forbidden)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from telegram.error import Forbidden

from src.config import Settings
from src.dispatcher import AlertDispatcher
from src.models import NewsItem, Priority, SourceSummary
from src.storage import BotStorage


class FakeBot:
    def __init__(self, forbidden_chats: set[int] | None = None) -> None:
        self.sent: list[dict[str, Any]] = []
        self.forbidden_chats = forbidden_chats or set()

    async def send_message(self, **kwargs: Any) -> None:
        if int(kwargs["chat_id"]) in self.forbidden_chats:
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
