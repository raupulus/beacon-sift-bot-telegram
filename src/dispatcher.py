"""Motor de distribución selectiva de alertas hacia los chats/canales suscritos."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from telegram import LinkPreviewOptions
from telegram.constants import ParseMode
from telegram.error import Forbidden, RetryAfter, TelegramError

from src.config import Settings
from src.formatter import format_news_item
from src.models import NewsItem
from src.storage import BotStorage

logger = logging.getLogger(__name__)


class AlertDispatcher:
    """Evalúa suscripciones en SQLite, deduplica y envía alertas por Telegram."""

    def __init__(self, bot: Any, storage: BotStorage, settings: Settings) -> None:
        self.bot = bot
        self.storage = storage
        self.settings = settings

    async def dispatch_item(self, item: NewsItem) -> int:
        """Envía una noticia nueva a todos los destinos que cumplan tipo, prioridad y pausa."""
        targets = await self.storage.get_matching_targets(item.type, item.priority_weight)
        if not targets:
            return 0

        text = format_news_item(item, self.settings.bot_timezone)
        preview_options = LinkPreviewOptions(is_disabled=self.settings.telegram_disable_web_preview)
        delivered = 0

        for target in targets:
            if await self.storage.was_dispatched(target.chat_id, target.thread_id, item.id):
                continue

            sent = await self._send_with_retry(
                chat_id=target.chat_id,
                thread_id=target.thread_id,
                text=text,
                preview_options=preview_options,
            )
            if sent:
                await self.storage.mark_dispatched(target.chat_id, target.thread_id, item.id)
                delivered += 1

        return delivered

    async def _send_with_retry(
        self,
        *,
        chat_id: int,
        thread_id: int,
        text: str,
        preview_options: LinkPreviewOptions,
    ) -> bool:
        kwargs: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": ParseMode.HTML,
            "link_preview_options": preview_options,
        }
        if thread_id > 0:
            kwargs["message_thread_id"] = thread_id

        try:
            await self.bot.send_message(**kwargs)
            return True
        except RetryAfter as exc:
            wait_seconds = min(max(float(exc.retry_after), 0.1), 15.0)
            logger.warning(
                "Telegram rate limit hit for chat %s; retrying in %ss", chat_id, wait_seconds
            )
            await asyncio.sleep(wait_seconds)
            try:
                await self.bot.send_message(**kwargs)
                return True
            except TelegramError as retry_exc:
                logger.warning("Retry failed sending alert to chat %s: %s", chat_id, retry_exc)
                return False
        except Forbidden:
            logger.warning("Bot blocked or removed from chat %s; pausing deliveries.", chat_id)
            await self.storage.set_paused(chat_id, thread_id, True)
            return False
        except TelegramError as exc:
            logger.warning("Failed sending alert to chat %s: %s", chat_id, exc)
            return False
