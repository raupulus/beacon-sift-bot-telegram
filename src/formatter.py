"""Formateo seguro en HTML de Telegram para mensajes y respuestas del contrato."""

from __future__ import annotations

import html
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.models import ApiStatus, NewsItem, Priority, SourceInfo, Subscription, TypeInfo

TELEGRAM_SAFE_MAX_LENGTH = 4000


def escape_html(text: str) -> str:
    """Escapa caracteres especiales para ParseMode.HTML de Telegram."""
    return html.escape(text, quote=True)


def safe_http_url(url: str | None) -> str | None:
    """Valida que la URL tenga esquema HTTP o HTTPS antes de enlazarla en HTML."""
    if not url:
        return None
    clean = url.strip()
    parsed = urlparse(clean)
    if parsed.scheme.lower() in {"http", "https"} and parsed.netloc:
        return clean
    return None


def _get_zone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def format_datetime(dt: datetime | None, timezone_name: str = "Europe/Madrid") -> str:
    """Formatea una fecha ISO en dd/mm/YYYY HH:MM según la zona horaria."""
    if dt is None:
        return "Fecha desconocida"
    return dt.astimezone(_get_zone(timezone_name)).strftime("%d/%m/%Y %H:%M")


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 1:
        return ""
    clean = " ".join(text.split())
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 1].rstrip() + "…"


def format_news_item(item: NewsItem, timezone_name: str = "Europe/Madrid") -> str:
    """Formatea una noticia individual cumpliendo el contrato mínimo de BOT_COMMANDS_CONTRACT."""
    badge = f"{item.priority.emoji} <b>{escape_html(item.priority.label_es.upper())}</b>"
    type_tag = f"<code>#{escape_html(item.type or 'general')}</code>"
    header = f"{badge} · {type_tag}"

    safe_url = safe_http_url(item.url)
    title_html = escape_html(item.title or "Sin titular")
    if safe_url is not None:
        title_line = f'<a href="{escape_html(safe_url)}"><b>{title_html}</b></a>'
    else:
        title_line = f"<b>{title_html}</b>"

    source_name = escape_html(item.source.name if item.source else "Fuente externa")
    date_str = escape_html(format_datetime(item.published_at, timezone_name))
    meta_line = f"<i>{source_name}</i> · {date_str}"

    parts = [header, title_line]
    snippet_text = item.snippet.strip() if item.snippet else ""
    if snippet_text:
        base_len = len(header) + len(title_line) + len(meta_line) + 12
        budget = max(80, TELEGRAM_SAFE_MAX_LENGTH - base_len)
        parts.append(escape_html(_truncate_text(snippet_text, min(320, budget))))

    parts.append(meta_line)
    message = "\n\n".join(parts)
    if len(message) <= TELEGRAM_SAFE_MAX_LENGTH:
        return message
    return message[: TELEGRAM_SAFE_MAX_LENGTH - 1] + "…"


def format_news_list(
    items: list[NewsItem],
    header: str,
    timezone_name: str = "Europe/Madrid",
) -> str:
    """Formatea un listado de noticias (/latest o /search) bajo el límite de Telegram."""
    lines = [f"<b>{escape_html(header)}</b>"]

    for idx, item in enumerate(items, start=1):
        safe_url = safe_http_url(item.url)
        title_html = escape_html(_truncate_text(item.title or "Sin titular", 160))
        link_html = (
            f'<a href="{escape_html(safe_url)}"><b>{title_html}</b></a>'
            if safe_url
            else f"<b>{title_html}</b>"
        )
        source_name = escape_html(item.source.name if item.source else "Fuente externa")
        date_str = escape_html(format_datetime(item.published_at, timezone_name))
        meta = (
            f"{item.priority.emoji} <code>#{escape_html(item.type)}</code> · "
            f"{escape_html(item.priority.value)} · {source_name} · {date_str}"
        )
        block = f"\n<b>{idx}.</b> {link_html}\n{meta}"

        if item.snippet:
            block += f"\n<i>{escape_html(_truncate_text(item.snippet, 120))}</i>"

        candidate = "\n".join(lines) + "\n" + block
        if len(candidate) > TELEGRAM_SAFE_MAX_LENGTH:
            break
        lines.append(block)

    return "\n".join(lines)


def format_help() -> str:
    """Ayuda oficial con los comandos del contrato BOT_COMMANDS_CONTRACT.md."""
    return (
        "<b>beacon-sift · Comandos disponibles</b>\n\n"
        "<b>Consultas públicas:</b>\n"
        "• /help — Muestra esta ayuda.\n"
        "• /status — Estado del bot, WebSocket y API web.\n"
        "• /sources [type] — Lista las fuentes activas.\n"
        "• /types — Lista tipos de fuente y prioridades válidas.\n"
        "• /latest [type] [priority] [limit] — Últimas noticias (por defecto 5, máx. 10).\n"
        "• /search &lt;query&gt; [type] [limit] — Busca noticias por palabra clave.\n\n"
        "<b>Suscripciones del canal (administradores):</b>\n"
        "• /subscribe &lt;type|all&gt; [min_priority] — "
        "Suscribe el canal (default: <code>low</code>).\n"
        "• /unsubscribe &lt;type|all&gt; — Elimina una o todas las suscripciones.\n"
        "• /filters — Muestra los filtros activos del canal.\n"
        "• /pause — Pausa las alertas automáticas sin borrar filtros.\n"
        "• /resume — Reanuda las alertas automáticas.\n\n"
        "<i>Prioridades válidas: low, medium, high, critical</i>"
    )


def format_status(
    api_status: ApiStatus | None,
    ws_connected: bool,
    last_event_at: datetime | None,
    timezone_name: str = "Europe/Madrid",
) -> str:
    """Formatea el mensaje de /status."""
    ws_state = "🟢 Conectado" if ws_connected else "🟡 Desconectado (reintentando)"
    last_ev = (
        escape_html(format_datetime(last_event_at, timezone_name))
        if last_event_at
        else "Sin eventos aún"
    )

    if api_status is None:
        return (
            "<b>Estado de beacon-sift</b>\n\n"
            "• Bot Telegram: 🟢 Operativo\n"
            f"• WebSocket Reverb: {ws_state}\n"
            "• API web: 🔴 No disponible en este momento\n"
            f"• Última alerta recibida: {last_ev}"
        )

    last_sync = (
        escape_html(format_datetime(api_status.last_sync_at, timezone_name))
        if api_status.last_sync_at
        else "Pendiente"
    )
    api_badge = "🟢 OK" if api_status.status == "ok" else f"🟠 {escape_html(api_status.status)}"

    return (
        "<b>Estado de beacon-sift</b>\n\n"
        "• Bot Telegram: 🟢 Operativo\n"
        f"• API web: {api_badge} (BD: <code>{escape_html(api_status.database)}</code>)\n"
        f"• WebSocket Reverb: {ws_state} "
        f"(canal <code>{escape_html(api_status.ws_channel)}</code>)\n"
        f"• Fuentes activas: <b>{api_status.sources_active}</b> / {api_status.sources_total}"
        f" (con fallos: {api_status.sources_failing})\n"
        f"• Noticias indexadas: <b>{api_status.items_total}</b>\n"
        f"• Última sincronización web: {last_sync}\n"
        f"• Última alerta en vivo: {last_ev}"
    )


def format_sources(sources: list[SourceInfo], filter_type: str | None = None) -> str:
    """Formatea la respuesta de /sources [type]."""
    if not sources:
        if filter_type:
            return f"No hay fuentes activas para el tipo <code>{escape_html(filter_type)}</code>."
        return "No hay fuentes activas configuradas en este momento."

    title = f"Fuentes activas (#{escape_html(filter_type)})" if filter_type else "Fuentes activas"
    lines = [f"<b>{title}</b> ({len(sources)})"]

    for src in sources:
        health = "🟢" if src.consecutive_failures == 0 else "🟠"
        safe_url = safe_http_url(src.url)
        name_html = escape_html(src.name)
        link = f'<a href="{escape_html(safe_url)}">{name_html}</a>' if safe_url else name_html
        entry = (
            f"{health} {link} — <code>#{escape_html(src.type)}</code> · "
            f"{escape_html(src.priority.value)} · {src.interval_minutes}m"
        )
        if len("\n".join(lines) + "\n" + entry) > TELEGRAM_SAFE_MAX_LENGTH:
            lines.append("<i>… listado truncado por límite de Telegram.</i>")
            break
        lines.append(entry)

    return "\n".join(lines)


def format_types(types: list[TypeInfo], priorities: list[Priority]) -> str:
    """Formatea la respuesta de /types."""
    if not types:
        type_block = "• <i>No hay tipos activos disponibles ahora mismo.</i>"
    else:
        type_block = "\n".join(
            f"• <code>{escape_html(t.type)}</code> — {t.sources_count} fuente(s), "
            f"{t.items_count} noticia(s)"
            for t in types
        )

    prio_block = "\n".join(
        f"• {p.emoji} <code>{p.value}</code> ({escape_html(p.label_es)})" for p in priorities
    )

    return (
        "<b>Tipos de fuente disponibles</b>\n"
        f"{type_block}\n\n"
        "<b>Niveles de prioridad válidos</b>\n"
        f"{prio_block}"
    )


def format_filters(subscriptions: list[Subscription], paused: bool) -> str:
    """Formatea la respuesta de /filters."""
    state_line = (
        "⏸️ <b>Estado del envío automático:</b> Pausado (usa /resume para reanudar)"
        if paused
        else "▶️ <b>Estado del envío automático:</b> Activo"
    )
    if not subscriptions:
        return (
            "<b>Filtros del canal actual</b>\n\n"
            f"{state_line}\n\n"
            "No hay suscripciones activas en este canal.\n"
            "Usa <code>/subscribe &lt;type|all&gt; [min_priority]</code> para activarlas."
        )

    rows = "\n".join(
        f"• <code>{escape_html(sub.source_type)}</code> — prioridad mínima: "
        f"{sub.min_priority.emoji} <code>{sub.min_priority.value}</code> "
        f"({escape_html(sub.min_priority.label_es)})"
        for sub in subscriptions
    )
    return f"<b>Filtros del canal actual</b>\n\n{state_line}\n\n{rows}"
