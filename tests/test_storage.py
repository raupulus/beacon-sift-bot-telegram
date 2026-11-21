"""Pruebas unitarias para la persistencia SQLite del bot de Telegram."""

from __future__ import annotations

from pathlib import Path

from src.models import ChatTarget, Priority
from src.storage import BotStorage


async def test_subscribe_update_and_unsubscribe(tmp_path: Path) -> None:
    storage = BotStorage(tmp_path / "bot.db")
    await storage.initialize()
    try:
        await storage.subscribe(-1001, 0, "cve", Priority.MEDIUM, title="Canal Sec")
        await storage.subscribe(-1001, 0, "linux", Priority.LOW)
        # Actualizar min_priority en cve
        await storage.subscribe(-1001, 0, "cve", Priority.HIGH)

        subs = await storage.list_subscriptions(-1001, 0)
        assert len(subs) == 2
        assert subs[0].source_type == "cve"
        assert subs[0].min_priority == Priority.HIGH
        assert subs[1].source_type == "linux"

        removed_one = await storage.unsubscribe(-1001, 0, "linux")
        assert removed_one == 1
        assert len(await storage.list_subscriptions(-1001, 0)) == 1

        # Añadir otra y eliminar todas con 'all'
        await storage.subscribe(-1001, 0, "all", Priority.CRITICAL)
        removed_all = await storage.unsubscribe(-1001, 0, "all")
        assert removed_all == 2
        assert await storage.list_subscriptions(-1001, 0) == []
    finally:
        await storage.close()


async def test_matching_targets_respects_priority_pause_and_dedup(tmp_path: Path) -> None:
    storage = BotStorage(tmp_path / "bot.db")
    await storage.initialize()
    try:
        # Chat 1 suscrito a 'cve' >= high y a 'all' >= low -> no debe duplicar destino
        await storage.subscribe(-1001, 10, "cve", Priority.HIGH)
        await storage.subscribe(-1001, 10, "all", Priority.LOW)

        # Chat 2 suscrito a 'cve' >= critical
        await storage.subscribe(-1002, 0, "cve", Priority.CRITICAL)

        # Chat 3 suscrito a 'cve' >= low pero pausado
        await storage.subscribe(-1003, 0, "cve", Priority.LOW)
        await storage.set_paused(-1003, 0, True)

        targets_high = await storage.get_matching_targets("cve", Priority.HIGH.weight)
        assert targets_high == [ChatTarget(chat_id=-1001, thread_id=10)]

        targets_critical = await storage.get_matching_targets("cve", Priority.CRITICAL.weight)
        assert targets_critical == [
            ChatTarget(chat_id=-1002, thread_id=0),
            ChatTarget(chat_id=-1001, thread_id=10),
        ]

        # Reanudar chat 3
        await storage.set_paused(-1003, 0, False)
        assert not await storage.is_paused(-1003, 0)
        targets_after_resume = await storage.get_matching_targets("cve", Priority.LOW.weight)
        assert ChatTarget(chat_id=-1003, thread_id=0) in targets_after_resume
    finally:
        await storage.close()


async def test_dispatched_deduplication_and_watermark(tmp_path: Path) -> None:
    storage = BotStorage(tmp_path / "bot.db")
    await storage.initialize()
    try:
        assert await storage.get_last_item_id() is None
        await storage.set_last_item_id(15)
        await storage.set_last_item_id(10)  # No retrocede
        assert await storage.get_last_item_id() == 15

        assert not await storage.was_dispatched(-1001, 0, 99)
        await storage.mark_dispatched(-1001, 0, 99)
        await storage.mark_dispatched(-1001, 0, 99)  # Idempotente
        assert await storage.was_dispatched(-1001, 0, 99)

        await storage.mark_dispatched(-1001, 0, 100)
        # Simular una fila antigua de hace 45 días para verificar poda por retención
        await storage._db().execute(
            "UPDATE dispatched_items SET dispatched_at = ? WHERE item_id = ?",
            ("2020-01-01T00:00:00+00:00", 99),
        )
        await storage._db().commit()

        deleted = await storage.prune_dispatched(retention_days=30)
        assert deleted == 1
        assert await storage.was_dispatched(-1001, 0, 99) is False
        assert await storage.was_dispatched(-1001, 0, 100) is True
    finally:
        await storage.close()


async def test_migrate_chat_id_transfers_subscriptions_pause_and_dispatched(
    tmp_path: Path,
) -> None:
    storage = BotStorage(tmp_path / "bot.db")
    await storage.initialize()
    try:
        await storage.subscribe(-200, 0, "cve", Priority.HIGH, title="Grupo Antiguo")
        await storage.subscribe(-200, 7, "iot", Priority.LOW, title="Topic IoT")
        await storage.set_paused(-200, 7, True)
        await storage.mark_dispatched(-200, 0, 501)

        await storage.migrate_chat_id(-200, -100200)

        assert await storage.list_subscriptions(-200, 0) == []
        assert await storage.was_dispatched(-200, 0, 501) is False

        subs_main = await storage.list_subscriptions(-100200, 0)
        assert len(subs_main) == 1
        assert subs_main[0].source_type == "cve"
        assert subs_main[0].min_priority == Priority.HIGH

        subs_topic = await storage.list_subscriptions(-100200, 7)
        assert len(subs_topic) == 1
        assert subs_topic[0].source_type == "iot"
        assert await storage.is_paused(-100200, 7) is True
        assert await storage.was_dispatched(-100200, 0, 501) is True
    finally:
        await storage.close()
