"""Registro de comandos de Telegram y contexto compartido de aplicación."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from telegram import BotCommand, LinkPreviewOptions, Update
from telegram.ext import Application, CommandHandler

from src.api_client import BeaconApiClient
from src.config import Settings
from src.dispatcher import AlertDispatcher
from src.storage import BotStorage

if TYPE_CHECKING:
    from src.reverb_client import ReverbListener


@dataclass(slots=True)
class BotAppContext:
    """Dependencias compartidas accesibles desde context.application.bot_data."""

    settings: Settings
    storage: BotStorage
    api_client: BeaconApiClient
    dispatcher: AlertDispatcher
    reverb_listener: ReverbListener


BOT_COMMANDS: list[BotCommand] = [
    BotCommand("help", "Muestra los comandos disponibles y ayuda de uso"),
    BotCommand("status", "Estado del bot, WebSocket Reverb y API web"),
    BotCommand("sources", "Lista las fuentes configuradas activas"),
    BotCommand("types", "Lista los tipos de fuente y prioridades válidas"),
    BotCommand("latest", "Últimas noticias filtrables por tipo, prioridad y límite"),
    BotCommand("search", "Busca noticias por palabra clave"),
    BotCommand("subscribe", "Suscribe el canal a un tipo o 'all' (Admin)"),
    BotCommand("unsubscribe", "Elimina una suscripción o todas (Admin)"),
    BotCommand("filters", "Muestra los filtros activos del canal actual"),
    BotCommand("pause", "Pausa las alertas automáticas en este canal (Admin)"),
    BotCommand("resume", "Reanuda las alertas automáticas en este canal (Admin)"),
]


def get_app_context(application: Application) -> BotAppContext:
    """Obtiene el contexto tipado desde application.bot_data."""
    ctx = application.bot_data.get("app_ctx")
    if not isinstance(ctx, BotAppContext):
        raise RuntimeError("BotAppContext no inicializado en application.bot_data.")
    return ctx


def get_thread_id(update: Update) -> int:
    """Extrae el message_thread_id del mensaje efectivo (0 si no aplica)."""
    message = update.effective_message
    if message is None:
        return 0
    return int(getattr(message, "message_thread_id", None) or 0)


async def reply_html(
    update: Update,
    text: str,
    *,
    disable_preview: bool = True,
) -> None:
    """Responde en HTML seguro sobre message o channel_post."""
    message = update.effective_message
    if message is None:
        return
    await message.reply_html(
        text,
        link_preview_options=LinkPreviewOptions(is_disabled=disable_preview),
    )


def register_handlers(application: Application) -> None:
    """Registra exactamente los 11 comandos definidos en BOT_COMMANDS_CONTRACT.md."""
    from src.handlers.info import (
        help_command,
        latest_command,
        search_command,
        sources_command,
        status_command,
        types_command,
    )
    from src.handlers.subscriptions import (
        filters_command,
        pause_command,
        resume_command,
        subscribe_command,
        unsubscribe_command,
    )

    handlers = [
        CommandHandler("help", help_command),
        CommandHandler("status", status_command),
        CommandHandler("sources", sources_command),
        CommandHandler("types", types_command),
        CommandHandler("latest", latest_command),
        CommandHandler("search", search_command),
        CommandHandler("subscribe", subscribe_command),
        CommandHandler("unsubscribe", unsubscribe_command),
        CommandHandler("filters", filters_command),
        CommandHandler("pause", pause_command),
        CommandHandler("resume", resume_command),
    ]
    for handler in handlers:
        application.add_handler(handler)
