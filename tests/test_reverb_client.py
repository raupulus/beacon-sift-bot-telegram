"""Tests unitarios para ReverbListener (protocolo Pusher v7 y catch-up)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from src.api_client import BeaconApiClient
from src.models import NewsItem
from src.reverb_client import ReverbListener
from src.storage import BotStorage


def _sample_item_dict(item_id: int, title: str = "Kernel update") -> dict[str, object]:
    return {
        "id": item_id,
        "title": title,
        "url": f"https://example.org/news/{item_id}",
        "snippet": "Resumen breve",
        "type": "linux",
        "priority": "medium",
        "priority_weight": 2,
        "published_at": "2026-11-20T12:00:00+00:00",
        "fetched_at": "2026-11-20T12:01:00+00:00",
        "source": {
            "slug": "kernel-releases",
            "name": "Linux Kernel Releases",
            "url": "https://www.kernel.org/feeds/kdist.xml",
        },
    }


async def test_reverb_listener_handshake_ping_and_news_created(tmp_path: Path) -> None:
    storage = BotStorage(tmp_path / "bot.db")
    await storage.initialize()

    def api_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/items":
            return httpx.Response(200, json={"data": [_sample_item_dict(10)]})
        return httpx.Response(404)

    api_client = BeaconApiClient(
        "http://localhost:8000", transport=httpx.MockTransport(api_handler)
    )
    received: list[NewsItem] = []

    async def on_item(item: NewsItem) -> None:
        received.append(item)

    listener = ReverbListener(
        ws_url="ws://localhost:8080",
        app_key="test-key",
        channel="beacon.news",
        api_client=api_client,
        storage=storage,
        on_item=on_item,
    )

    sent_frames: list[dict[str, object]] = []

    async def fake_send(msg: str) -> None:
        sent_frames.append(json.loads(msg))

    try:
        assert (
            listener.build_ws_endpoint()
            == "ws://localhost:8080/app/test-key?protocol=7&client=beacon-telegram&version=1.0"
        )

        # 1. Handshake -> subscribe
        await listener.handle_raw_message(
            json.dumps({"event": "pusher:connection_established", "data": "{}"}),
            fake_send,
        )
        assert sent_frames[-1] == {
            "event": "pusher:subscribe",
            "data": {"channel": "beacon.news"},
        }

        # 2. Suscripción exitosa -> primer arranque fija watermark a 10 sin spammear histórico
        await listener.handle_raw_message(
            json.dumps(
                {"event": "pusher_internal:subscription_succeeded", "channel": "beacon.news"}
            ),
            fake_send,
        )
        assert listener.is_connected is True
        assert await storage.get_last_item_id() == 10
        assert received == []

        # 3. Ping -> Pong
        await listener.handle_raw_message(json.dumps({"event": "pusher:ping"}), fake_send)
        assert sent_frames[-1] == {"event": "pusher:pong", "data": {}}

        # 4. Evento news.created -> llama on_item y actualiza watermark a 11
        item = await listener.handle_raw_message(
            json.dumps(
                {
                    "event": "news.created",
                    "channel": "beacon.news",
                    "data": json.dumps({"item": _sample_item_dict(11, "Live CVE Alert")}),
                }
            ),
            fake_send,
        )
        assert item is not None
        assert len(received) == 1
        assert received[0].id == 11
        assert await storage.get_last_item_id() == 11
    finally:
        await api_client.close()
        await storage.close()


async def test_reverb_listener_catchup_dispatches_missed_items_on_reconnect(tmp_path: Path) -> None:
    storage = BotStorage(tmp_path / "bot.db")
    await storage.initialize()
    await storage.set_last_item_id(10)

    def api_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("since_id") == "10"
        assert request.url.params.get("order") == "asc"
        return httpx.Response(
            200,
            json={"data": [_sample_item_dict(11, "Missed 1"), _sample_item_dict(12, "Missed 2")]},
        )

    api_client = BeaconApiClient(
        "http://localhost:8000", transport=httpx.MockTransport(api_handler)
    )
    received_ids: list[int] = []

    async def on_item(item: NewsItem) -> None:
        received_ids.append(item.id)

    listener = ReverbListener(
        ws_url="ws://localhost:8080",
        app_key="test-key",
        channel="beacon.news",
        api_client=api_client,
        storage=storage,
        on_item=on_item,
    )

    try:
        count = await listener.run_catchup()
        assert count == 2
        assert received_ids == [11, 12]
        assert await storage.get_last_item_id() == 12
    finally:
        await api_client.close()
        await storage.close()
