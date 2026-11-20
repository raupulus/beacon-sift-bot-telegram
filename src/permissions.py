"""Control de permisos para comandos de suscripción y gestión de canal."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from src.config import Settings

logger = logging.getLogger(__name__)


async def can_manage_subscriptions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    settings: Settings,
) -> bool:
    """Comprueba si quien ejecuta el comando tiene permiso de administración en el destino."""
    if update.channel_post is not None or update.edited_channel_post is not None:
        return True

    user = update.effective_user
    chat = update.effective_chat

    if user is not None and user.id in settings.admin_ids:
        return True

    if chat is None:
        return False

    if chat.type == ChatType.PRIVATE:
        return settings.allow_private_subscriptions

    if user is None:
        return False

    if chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}:
        try:
            member = await context.bot.get_chat_member(chat.id, user.id)
        except TelegramError as exc:
            logger.warning("Failed to verify member %s in chat %s: %s", user.id, chat.id, exc)
            return False

        return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}

    return False
