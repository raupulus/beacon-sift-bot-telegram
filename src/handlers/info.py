"""Comandos públicos de consulta (/help, /status, /sources, /types, /latest, /search)."""

from __future__ import annotations

import re

from telegram import Update
from telegram.ext import ContextTypes

from src.api_client import WebApiUnavailableError
from src.formatter import (
    escape_html,
    format_help,
    format_news_list,
    format_sources,
    format_status,
    format_types,
)
from src.handlers import get_app_context, reply_html
from src.models import Priority

_API_UNAVAILABLE_MSG = (
    "⚠️ La API de <b>beacon-sift</b> no está disponible en este momento. "
    "Inténtalo de nuevo en unos instantes."
)


def _is_int_token(token: str) -> bool:
    return bool(re.fullmatch(r"[+-]?\d+", token.strip()))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Implementa /help."""
    await reply_html(update, format_help())


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Implementa /status."""
    app_ctx = get_app_context(context.application)
    api_status = None
    try:
        api_status = await app_ctx.api_client.get_status()
    except WebApiUnavailableError:
        api_status = None

    text = format_status(
        api_status=api_status,
        ws_connected=app_ctx.reverb_listener.is_connected,
        last_event_at=app_ctx.reverb_listener.last_event_at,
        timezone_name=app_ctx.settings.bot_timezone,
    )
    await reply_html(update, text)


async def sources_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Implementa /sources [type]."""
    args = context.args or []
    if len(args) > 1:
        await reply_html(
            update,
            "Uso incorrecto de parámetros.\nUso esperado: <code>/sources [type]</code>",
        )
        return

    filter_type = args[0].strip().lower() if args else None
    app_ctx = get_app_context(context.application)
    try:
        sources = await app_ctx.api_client.get_sources(source_type=filter_type)
    except WebApiUnavailableError:
        await reply_html(update, _API_UNAVAILABLE_MSG)
        return

    await reply_html(update, format_sources(sources, filter_type))


async def types_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Implementa /types."""
    app_ctx = get_app_context(context.application)
    try:
        types, priorities = await app_ctx.api_client.get_types()
    except WebApiUnavailableError:
        await reply_html(update, _API_UNAVAILABLE_MSG)
        return

    await reply_html(update, format_types(types, priorities))


async def latest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Implementa /latest [type] [priority] [limit]."""
    args = list(context.args or [])
    limit = 5
    source_type: str | None = None
    min_priority: Priority | None = None

    if args and _is_int_token(args[-1]):
        parsed_limit = int(args.pop())
        if parsed_limit < 1 or parsed_limit > 10:
            await reply_html(
                update,
                "Parámetro <code>limit</code> inválido (debe estar entre 1 y 10).\n"
                "Uso esperado: <code>/latest [type] [priority] [limit]</code>",
            )
            return
        limit = parsed_limit

    for token in args:
        parsed_prio = Priority.parse(token)
        if parsed_prio is not None:
            if min_priority is not None:
                await reply_html(
                    update,
                    "Has indicado más de una prioridad.\n"
                    "Uso esperado: <code>/latest [type] [priority] [limit]</code>",
                )
                return
            min_priority = parsed_prio
        else:
            if source_type is not None:
                await reply_html(
                    update,
                    f"Parámetro inesperado: <code>{escape_html(token)}</code>.\n"
                    "Uso esperado: <code>/latest [type] [priority] [limit]</code>",
                )
                return
            source_type = token.strip().lower()

    app_ctx = get_app_context(context.application)
    try:
        items = await app_ctx.api_client.get_items(
            source_type=source_type,
            min_priority=min_priority,
            per_page=limit,
        )
    except WebApiUnavailableError:
        await reply_html(update, _API_UNAVAILABLE_MSG)
        return

    if not items:
        await reply_html(update, "No hay noticias disponibles para los filtros indicados.")
        return

    header = "Últimas noticias"
    if source_type:
        header += f" · #{source_type}"
    if min_priority:
        header += f" · >={min_priority.value}"

    await reply_html(
        update,
        format_news_list(items, header, app_ctx.settings.bot_timezone),
        disable_preview=app_ctx.settings.telegram_disable_web_preview,
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Implementa /search <query> [type] [limit]."""
    args = list(context.args or [])
    if not args:
        await reply_html(
            update,
            "Falta el término de búsqueda <code>&lt;query&gt;</code>.\n"
            "Uso esperado: <code>/search &lt;query&gt; [type] [limit]</code>",
        )
        return

    limit = 5
    if len(args) >= 2 and _is_int_token(args[-1]):
        parsed_limit = int(args.pop())
        if parsed_limit < 1 or parsed_limit > 10:
            await reply_html(
                update,
                "Parámetro <code>limit</code> inválido (debe estar entre 1 y 10).\n"
                "Uso esperado: <code>/search &lt;query&gt; [type] [limit]</code>",
            )
            return
        limit = parsed_limit

    app_ctx = get_app_context(context.application)
    source_type: str | None = None

    try:
        if len(args) >= 2:
            types, _ = await app_ctx.api_client.get_types()
            valid_types = {t.type for t in types}
            candidate = args[-1].strip().lower()
            if candidate in valid_types:
                source_type = candidate
                args.pop()

        query = " ".join(args).strip()
        if not query:
            await reply_html(
                update,
                "Falta el término de búsqueda <code>&lt;query&gt;</code>.\n"
                "Uso esperado: <code>/search &lt;query&gt; [type] [limit]</code>",
            )
            return

        items = await app_ctx.api_client.get_items(
            source_type=source_type,
            query=query,
            per_page=limit,
        )
    except WebApiUnavailableError:
        await reply_html(update, _API_UNAVAILABLE_MSG)
        return

    if not items:
        await reply_html(
            update,
            f"No se encontraron noticias para <code>{escape_html(query)}</code>.",
        )
        return

    header = f"Resultados para '{query}'"
    if source_type:
        header += f" · #{source_type}"

    await reply_html(
        update,
        format_news_list(items, header, app_ctx.settings.bot_timezone),
        disable_preview=app_ctx.settings.telegram_disable_web_preview,
    )
