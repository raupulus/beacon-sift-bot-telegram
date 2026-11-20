"""Comandos de gestión del canal (/subscribe, /unsubscribe, /filters, /pause, /resume)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from src.api_client import WebApiUnavailableError
from src.formatter import escape_html, format_filters
from src.handlers import get_app_context, get_thread_id, reply_html
from src.models import Priority
from src.permissions import can_manage_subscriptions

_DENIED_MSG = "⛔ Este comando está restringido a administradores del canal o del bot."
_API_UNAVAILABLE_MSG = (
    "⚠️ No se pudo validar el tipo con la API de <b>beacon-sift</b>. "
    "Inténtalo de nuevo en unos instantes."
)


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Implementa /subscribe <type|all> [min_priority]."""
    app_ctx = get_app_context(context.application)
    if not await can_manage_subscriptions(update, context, app_ctx.settings):
        await reply_html(update, _DENIED_MSG)
        return

    args = list(context.args or [])
    if len(args) not in {1, 2}:
        await reply_html(
            update,
            "Parámetros incorrectos.\n"
            "Uso esperado: <code>/subscribe &lt;type|all&gt; [min_priority]</code>",
        )
        return

    target_type = args[0].strip().lower()
    min_priority = Priority.LOW

    if len(args) == 2:
        parsed_prio = Priority.parse(args[1])
        if parsed_prio is None:
            await reply_html(
                update,
                f"Prioridad inválida: <code>{escape_html(args[1])}</code>.\n"
                "Valores válidos: <code>low</code>, <code>medium</code>, "
                "<code>high</code>, <code>critical</code>.",
            )
            return
        min_priority = parsed_prio

    if target_type != "all":
        try:
            types, _ = await app_ctx.api_client.get_types()
        except WebApiUnavailableError:
            await reply_html(update, _API_UNAVAILABLE_MSG)
            return

        valid_types = {t.type for t in types}
        if target_type not in valid_types:
            available = ", ".join(sorted(valid_types)) or "ninguno"
            await reply_html(
                update,
                f"El tipo <code>{escape_html(target_type)}</code> no existe.\n"
                f"Tipos disponibles: <code>{escape_html(available)}</code> (o <code>all</code>).",
            )
            return

    chat = update.effective_chat
    if chat is None:
        return
    thread_id = get_thread_id(update)
    await app_ctx.storage.subscribe(
        chat.id,
        thread_id,
        target_type,
        min_priority,
        title=getattr(chat, "title", None),
    )

    await reply_html(
        update,
        f"✅ Suscripción guardada para <code>{escape_html(target_type)}</code> "
        f"con prioridad mínima {min_priority.emoji} <code>{min_priority.value}</code>.",
    )


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Implementa /unsubscribe <type|all>."""
    app_ctx = get_app_context(context.application)
    if not await can_manage_subscriptions(update, context, app_ctx.settings):
        await reply_html(update, _DENIED_MSG)
        return

    args = list(context.args or [])
    if len(args) != 1:
        await reply_html(
            update,
            "Parámetros incorrectos.\nUso esperado: <code>/unsubscribe &lt;type|all&gt;</code>",
        )
        return

    chat = update.effective_chat
    if chat is None:
        return
    target_type = args[0].strip().lower()
    thread_id = get_thread_id(update)
    removed = await app_ctx.storage.unsubscribe(chat.id, thread_id, target_type)

    if removed == 0:
        await reply_html(
            update,
            f"No había ninguna suscripción activa para <code>{escape_html(target_type)}</code>.",
        )
        return

    if target_type == "all":
        await reply_html(update, f"🗑️ Eliminadas todas las suscripciones ({removed}) de este canal.")
    else:
        await reply_html(
            update,
            f"🗑️ Suscripción eliminada para <code>{escape_html(target_type)}</code>.",
        )


async def filters_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Implementa /filters."""
    chat = update.effective_chat
    if chat is None:
        return
    app_ctx = get_app_context(context.application)
    thread_id = get_thread_id(update)
    subs = await app_ctx.storage.list_subscriptions(chat.id, thread_id)
    paused = await app_ctx.storage.is_paused(chat.id, thread_id)
    await reply_html(update, format_filters(subs, paused))


async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Implementa /pause."""
    app_ctx = get_app_context(context.application)
    if not await can_manage_subscriptions(update, context, app_ctx.settings):
        await reply_html(update, _DENIED_MSG)
        return

    chat = update.effective_chat
    if chat is None:
        return
    thread_id = get_thread_id(update)
    await app_ctx.storage.set_paused(chat.id, thread_id, True, title=getattr(chat, "title", None))
    await reply_html(
        update,
        "⏸️ Alertas automáticas pausadas en este canal. Los filtros se mantienen guardados.",
    )


async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Implementa /resume."""
    app_ctx = get_app_context(context.application)
    if not await can_manage_subscriptions(update, context, app_ctx.settings):
        await reply_html(update, _DENIED_MSG)
        return

    chat = update.effective_chat
    if chat is None:
        return
    thread_id = get_thread_id(update)
    await app_ctx.storage.set_paused(chat.id, thread_id, False, title=getattr(chat, "title", None))
    await reply_html(update, "▶️ Alertas automáticas reanudadas en este canal.")
