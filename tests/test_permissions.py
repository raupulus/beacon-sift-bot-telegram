"""Tests unitarios para el control de permisos de canales, grupos y admins anónimos."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError

from src.config import Settings
from src.permissions import can_manage_subscriptions


def _make_update(
    *,
    chat_id: int = -1001,
    chat_type: str = ChatType.SUPERGROUP,
    user_id: int | None = 10,
    sender_chat_id: int | None = None,
    channel_post: bool = False,
) -> SimpleNamespace:
    sender_chat = SimpleNamespace(id=sender_chat_id) if sender_chat_id is not None else None
    msg = SimpleNamespace(sender_chat=sender_chat)
    chat = SimpleNamespace(id=chat_id, type=chat_type)
    user = SimpleNamespace(id=user_id) if user_id is not None else None
    return SimpleNamespace(
        channel_post=msg if channel_post else None,
        edited_channel_post=None,
        effective_message=msg,
        effective_chat=chat,
        effective_user=user,
    )


def _make_context(
    *,
    status: str = ChatMemberStatus.MEMBER,
    raise_error: bool = False,
) -> SimpleNamespace:
    async def get_chat_member(chat_id: int, user_id: int) -> Any:
        if raise_error:
            raise TelegramError("Bad Request: chat_admin_required")
        return SimpleNamespace(status=status)

    return SimpleNamespace(bot=SimpleNamespace(get_chat_member=get_chat_member))


async def test_anonymous_supergroup_admin_is_allowed_and_foreign_sender_chat_denied() -> None:
    settings = Settings()

    u_anon = _make_update(chat_id=-10050, user_id=1087968824, sender_chat_id=-10050)
    assert await can_manage_subscriptions(u_anon, _make_context(), settings) is True

    u_foreign = _make_update(chat_id=-10050, user_id=136817688, sender_chat_id=-10099)
    assert await can_manage_subscriptions(u_foreign, _make_context(), settings) is False


async def test_get_chat_member_telegram_error_denies_safely() -> None:
    settings = Settings()
    u = _make_update(chat_id=-10050, user_id=77)
    assert await can_manage_subscriptions(u, _make_context(raise_error=True), settings) is False


async def test_global_admin_and_private_chat_flag() -> None:
    u_priv = _make_update(chat_id=77, chat_type=ChatType.PRIVATE, user_id=77)

    assert await can_manage_subscriptions(u_priv, _make_context(), Settings()) is False
    assert (
        await can_manage_subscriptions(
            u_priv, _make_context(), Settings(allow_private_subscriptions=True)
        )
        is True
    )
    assert (
        await can_manage_subscriptions(u_priv, _make_context(), Settings(telegram_admin_ids="77"))
        is True
    )
