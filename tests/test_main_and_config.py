"""Tests unitarios para configuración, parseo de fechas y ciclo de vida de main.py."""

from __future__ import annotations

import asyncio
from datetime import UTC
from pathlib import Path
from typing import Any

from src.config import Settings
from src.handlers import BOT_COMMANDS, get_app_context
from src.main import build_application
from src.models import _parse_iso_datetime


def test_settings_admin_ids_and_iso_datetime_parsing() -> None:
    settings = Settings(
        telegram_admin_ids=" 1001, abc , , 2002 ,-5 ",
        web_api_base_url="https://feed.raupulus.dev///",
        reverb_ws_url="wss://feed.raupulus.dev/",
        log_level=" debug ",
    )
    assert settings.admin_ids == {1001, 2002, -5}
    assert settings.web_api_base_url == "https://feed.raupulus.dev"
    assert settings.reverb_ws_url == "wss://feed.raupulus.dev"
    assert settings.log_level == "DEBUG"

    dt_z = _parse_iso_datetime("2026-11-21T10:00:00Z")
    assert dt_z is not None and dt_z.tzinfo == UTC
    dt_naive = _parse_iso_datetime("2026-11-21T10:00:00")
    assert dt_naive is not None and dt_naive.tzinfo == UTC
    assert _parse_iso_datetime("invalid-date") is None
    assert _parse_iso_datetime(None) is None


async def test_build_application_post_init_and_post_shutdown(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    settings = Settings(
        telegram_bot_token="123456:TESTTOKEN",
        bot_db_path=str(tmp_path / "bot.db"),
    )
    app = build_application(settings)
    app_ctx = get_app_context(app)

    recorded_commands: list[Any] = []
    reverb_started = asyncio.Event()

    async def fake_set_my_commands(bot_self: Any, commands: list[Any]) -> bool:
        recorded_commands.extend(commands)
        return True

    async def fake_run_forever(stop_event: asyncio.Event) -> None:
        reverb_started.set()
        await stop_event.wait()

    monkeypatch.setattr(type(app.bot), "set_my_commands", fake_set_my_commands)
    monkeypatch.setattr(app_ctx.reverb_listener, "run_forever", fake_run_forever)

    assert app.post_init is not None
    assert app.post_shutdown is not None

    await app.post_init(app)
    await asyncio.wait_for(reverb_started.wait(), timeout=2.0)

    assert [c.command for c in recorded_commands] == [c.command for c in BOT_COMMANDS]
    assert (tmp_path / "bot.db").exists()

    await app.post_shutdown(app)
    assert app.bot_data["reverb_task"].done()
