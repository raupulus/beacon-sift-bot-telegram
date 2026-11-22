"""Tests unitarios para todos los comandos del contrato BOT_COMMANDS_CONTRACT.md."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
from telegram import Chat, Message, MessageEntity, Update
from telegram.constants import ChatMemberStatus, ChatType
from telegram.ext import Application

from src.api_client import BeaconApiClient
from src.config import Settings
from src.dispatcher import AlertDispatcher
from src.handlers import BotAppContext, register_handlers
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
from src.models import Priority
from src.reverb_client import ReverbListener
from src.storage import BotStorage


class DummyMessage:
    def __init__(self, thread_id: int | None = None) -> None:
        self.message_thread_id = thread_id
        self.replies: list[str] = []

    async def reply_html(self, text: str, **kwargs: Any) -> None:
        self.replies.append(text)


def _make_update(
    *,
    chat_id: int = -1001,
    chat_type: str = ChatType.SUPERGROUP,
    user_id: int = 10,
    thread_id: int | None = None,
    is_channel_post: bool = False,
) -> tuple[SimpleNamespace, DummyMessage]:
    msg = DummyMessage(thread_id=thread_id)
    chat = SimpleNamespace(id=chat_id, type=chat_type, title="Grupo Tech")
    user = None if is_channel_post else SimpleNamespace(id=user_id)
    update = SimpleNamespace(
        effective_message=msg,
        effective_chat=chat,
        effective_user=user,
        channel_post=msg if is_channel_post else None,
        edited_channel_post=None,
    )
    return update, msg


def _make_context(
    app_ctx: BotAppContext,
    args: list[str] | None = None,
    member_status: str = ChatMemberStatus.ADMINISTRATOR,
) -> SimpleNamespace:
    async def get_chat_member(chat_id: int, user_id: int) -> SimpleNamespace:
        return SimpleNamespace(status=member_status)

    bot = SimpleNamespace(get_chat_member=get_chat_member)
    application = SimpleNamespace(bot_data={"app_ctx": app_ctx})
    return SimpleNamespace(args=args or [], application=application, bot=bot)


def _api_transport(*, fail: bool = False) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            return httpx.Response(503)

        if request.url.path == "/api/v1/status":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "database": "ok",
                    "last_sync_at": "2026-11-20T14:00:00+00:00",
                    "sources": {"active": 2, "failing": 0, "total": 2},
                    "items_total": 12,
                    "websocket": {"channel": "beacon.news", "event": "news.created"},
                },
            )
        if request.url.path == "/api/v1/types":
            return httpx.Response(
                200,
                json={
                    "types": [
                        {"type": "cve", "sources_count": 1, "items_count": 8},
                        {"type": "linux", "sources_count": 1, "items_count": 4},
                    ],
                    "priorities": [
                        {"value": "low", "label": "Baja", "weight": 1},
                        {"value": "medium", "label": "Media", "weight": 2},
                        {"value": "high", "label": "Alta", "weight": 3},
                        {"value": "critical", "label": "Crítica", "weight": 4},
                    ],
                },
            )
        if request.url.path == "/api/v1/sources":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "slug": "debian-security",
                            "name": "Debian Security",
                            "url": "https://www.debian.org/security/dsa",
                            "format": "rss",
                            "type": "cve",
                            "priority": "high",
                            "interval_minutes": 30,
                            "is_active": True,
                        }
                    ]
                },
            )
        if request.url.path == "/api/v1/items":
            if request.url.params.get("q") == "notfound":
                return httpx.Response(200, json={"data": []})
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 99,
                            "title": "DSA-99 OpenSSL update",
                            "url": "https://debian.org/dsa-99",
                            "snippet": "Resumen breve",
                            "type": "cve",
                            "priority": "high",
                            "priority_weight": 3,
                            "published_at": "2026-11-20T14:00:00+00:00",
                            "fetched_at": "2026-11-20T14:05:00+00:00",
                            "source": {
                                "slug": "debian-security",
                                "name": "Debian Security",
                                "url": "https://debian.org",
                            },
                        }
                    ]
                },
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


async def test_all_info_commands_and_validation(tmp_path: Path) -> None:
    storage = BotStorage(tmp_path / "bot.db")
    await storage.initialize()
    api_client = BeaconApiClient("http://localhost:8000", transport=_api_transport())
    settings = Settings()
    dispatcher = AlertDispatcher(SimpleNamespace(), storage, settings)
    reverb = ReverbListener(
        "ws://localhost:8080", "k", "beacon.news", api_client, storage, dispatcher.dispatch_item
    )
    reverb.is_connected = True
    app_ctx = BotAppContext(settings, storage, api_client, dispatcher, reverb)

    try:
        u, m = _make_update()
        await help_command(u, _make_context(app_ctx))
        assert "/subscribe" in m.replies[-1]

        await status_command(u, _make_context(app_ctx))
        assert "🟢 Conectado" in m.replies[-1]
        assert "Fuentes activas: <b>2</b>" in m.replies[-1]

        await sources_command(u, _make_context(app_ctx, ["cve"]))
        assert "Debian Security" in m.replies[-1]

        await types_command(u, _make_context(app_ctx))
        assert "cve" in m.replies[-1]
        assert "critical" in m.replies[-1]

        await latest_command(u, _make_context(app_ctx, ["cve", "high", "5"]))
        assert "DSA-99 OpenSSL update" in m.replies[-1]

        # limit fuera de rango
        await latest_command(u, _make_context(app_ctx, ["25"]))
        assert "inválido" in m.replies[-1]

        # /search con tipo opcional y límite
        await search_command(u, _make_context(app_ctx, ["OpenSSL", "cve", "5"]))
        assert "DSA-99 OpenSSL update" in m.replies[-1]

        # /search sin resultados
        await search_command(u, _make_context(app_ctx, ["notfound"]))
        assert "No se encontraron noticias" in m.replies[-1]

        # /search sin parámetros
        await search_command(u, _make_context(app_ctx, []))
        assert "Uso esperado" in m.replies[-1]
    finally:
        await api_client.close()
        await storage.close()


async def test_info_commands_handle_unavailable_api(tmp_path: Path) -> None:
    storage = BotStorage(tmp_path / "bot.db")
    await storage.initialize()
    api_client = BeaconApiClient("http://localhost:8000", transport=_api_transport(fail=True))
    settings = Settings()
    dispatcher = AlertDispatcher(SimpleNamespace(), storage, settings)
    reverb = ReverbListener(
        "ws://localhost:8080", "k", "beacon.news", api_client, storage, dispatcher.dispatch_item
    )
    app_ctx = BotAppContext(settings, storage, api_client, dispatcher, reverb)

    try:
        u, m = _make_update()
        await status_command(u, _make_context(app_ctx))
        assert "No disponible" in m.replies[-1]

        await latest_command(u, _make_context(app_ctx))
        assert "no está disponible" in m.replies[-1]
    finally:
        await api_client.close()
        await storage.close()


async def test_subscription_commands_permissions_and_lifecycle(tmp_path: Path) -> None:
    storage = BotStorage(tmp_path / "bot.db")
    await storage.initialize()
    api_client = BeaconApiClient("http://localhost:8000", transport=_api_transport())
    settings = Settings(allow_private_subscriptions=False)
    dispatcher = AlertDispatcher(SimpleNamespace(), storage, settings)
    reverb = ReverbListener(
        "ws://localhost:8080", "k", "beacon.news", api_client, storage, dispatcher.dispatch_item
    )
    app_ctx = BotAppContext(settings, storage, api_client, dispatcher, reverb)

    try:
        # Usuario no admin en grupo -> denegado
        u_member, m_member = _make_update(user_id=50)
        await subscribe_command(
            u_member,
            _make_context(app_ctx, ["cve", "high"], member_status=ChatMemberStatus.MEMBER),
        )
        assert "restringido a administradores" in m_member.replies[-1]

        # Usuario no admin en privado -> denegado
        u_priv, m_priv = _make_update(chat_type=ChatType.PRIVATE, user_id=50)
        await pause_command(u_priv, _make_context(app_ctx))
        assert "restringido a administradores" in m_priv.replies[-1]

        # Admin del grupo -> permitido; tipo inexistente rechazado
        u_admin, m_admin = _make_update(user_id=10, thread_id=5)
        await subscribe_command(u_admin, _make_context(app_ctx, ["desconocido"]))
        assert "no existe" in m_admin.replies[-1]

        # Suscripción válida
        await subscribe_command(u_admin, _make_context(app_ctx, ["cve", "high"]))
        assert "Suscripción guardada" in m_admin.replies[-1]

        # Pausar y reanudar
        await pause_command(u_admin, _make_context(app_ctx))
        assert "pausadas" in m_admin.replies[-1]
        await filters_command(u_admin, _make_context(app_ctx))
        assert "Pausado" in m_admin.replies[-1]
        await resume_command(u_admin, _make_context(app_ctx))
        assert "reanudadas" in m_admin.replies[-1]

        # Unsubscribe
        await unsubscribe_command(u_admin, _make_context(app_ctx, ["cve"]))
        assert "Suscripción eliminada" in m_admin.replies[-1]

        # Channel post -> permitido sin user_id
        u_chan, m_chan = _make_update(chat_type=ChatType.CHANNEL, is_channel_post=True)
        await subscribe_command(u_chan, _make_context(app_ctx, ["all", Priority.CRITICAL.value]))
        assert "Suscripción guardada" in m_chan.replies[-1]
    finally:
        await api_client.close()
        await storage.close()


def test_command_handlers_accept_channel_post_updates() -> None:
    app = Application.builder().token("123456:TESTTOKEN").build()
    app.bot._bot_user = SimpleNamespace(username="beacon_test_bot")
    register_handlers(app)

    msg = Message(
        message_id=10,
        date=datetime(2026, 11, 22, 17, 0, tzinfo=UTC),
        chat=Chat(id=-100123456, type=ChatType.CHANNEL),
        text="/subscribe all",
        entities=(MessageEntity(type=MessageEntity.BOT_COMMAND, offset=0, length=10),),
    )
    msg.set_bot(app.bot)
    update = Update(update_id=1, channel_post=msg)

    handlers = app.handlers[0]
    sub_handler = next(h for h in handlers if "subscribe" in getattr(h, "commands", ()))
    matched = sub_handler.check_update(update)
    assert matched is not None and matched is not False
    assert matched[0] == ["all"]
