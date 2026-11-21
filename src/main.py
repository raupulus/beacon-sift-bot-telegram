"""Punto de entrada principal de beacon-sift-bot-telegram."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys

from telegram import Update
from telegram.ext import Application

from src.api_client import BeaconApiClient
from src.config import Settings
from src.dispatcher import AlertDispatcher
from src.handlers import BOT_COMMANDS, BotAppContext, register_handlers
from src.reverb_client import ReverbListener
from src.storage import BotStorage


def configure_logging(level: str) -> None:
    """Configura logging estándar legible para consola y Docker."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def build_application(settings: Settings) -> Application:
    """Construye la aplicación de Telegram coordinada con SQLite, API v1 y Reverb."""
    storage = BotStorage(settings.bot_db_path)
    api_client = BeaconApiClient(
        base_url=settings.web_api_base_url,
        timeout_seconds=settings.web_api_timeout_seconds,
    )
    stop_event = asyncio.Event()

    async def post_init(app: Application) -> None:
        await storage.initialize()
        await storage.prune_dispatched(retention_days=30)
        await app.bot.set_my_commands(BOT_COMMANDS)

        app_ctx: BotAppContext = app.bot_data["app_ctx"]
        task = asyncio.create_task(
            app_ctx.reverb_listener.run_forever(stop_event),
            name="reverb-listener",
        )
        app.bot_data["reverb_task"] = task
        logging.getLogger(__name__).info("Telegram bot initialized and listening to Reverb.")

    async def post_shutdown(app: Application) -> None:
        stop_event.set()
        task = app.bot_data.get("reverb_task")
        if isinstance(task, asyncio.Task):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await api_client.close()
        await storage.close()
        logging.getLogger(__name__).info("beacon-sift-bot-telegram resources closed.")

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    dispatcher = AlertDispatcher(application.bot, storage, settings)
    reverb_listener = ReverbListener(
        ws_url=settings.reverb_ws_url,
        app_key=settings.reverb_app_key,
        channel=settings.reverb_channel,
        api_client=api_client,
        storage=storage,
        on_item=dispatcher.dispatch_item,
    )

    application.bot_data["app_ctx"] = BotAppContext(
        settings=settings,
        storage=storage,
        api_client=api_client,
        dispatcher=dispatcher,
        reverb_listener=reverb_listener,
    )
    register_handlers(application)
    return application


def main() -> None:
    """Arranca el bot en modo long polling."""
    settings = Settings()
    configure_logging(settings.log_level)

    if not settings.telegram_bot_token.strip():
        logging.getLogger(__name__).error(
            "Missing TELEGRAM_BOT_TOKEN in environment (.env). Aborting startup."
        )
        sys.exit(1)

    application = build_application(settings)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
