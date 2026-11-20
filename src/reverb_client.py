"""Cliente WebSocket async (protocolo Pusher v7) para Laravel Reverb en web/."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import websockets

from src.api_client import BeaconApiClient, WebApiUnavailableError
from src.models import NewsItem
from src.storage import BotStorage

logger = logging.getLogger(__name__)


class ReverbListener:
    """Escucha el canal público de Reverb y ejecuta catch-up tras reconexiones."""

    def __init__(
        self,
        ws_url: str,
        app_key: str,
        channel: str,
        api_client: BeaconApiClient,
        storage: BotStorage,
        on_item: Callable[[NewsItem], Awaitable[Any]],
    ) -> None:
        self.ws_url = ws_url.rstrip("/")
        self.app_key = app_key
        self.channel = channel
        self.api_client = api_client
        self.storage = storage
        self.on_item = on_item

        self.is_connected: bool = False
        self.last_event_at: datetime | None = None
        self.last_error: str | None = None

    def build_ws_endpoint(self) -> str:
        """Construye la URL WebSocket compatible con Laravel Reverb / Pusher v7."""
        return f"{self.ws_url}/app/{self.app_key}?protocol=7&client=beacon-telegram&version=1.0"

    async def handle_raw_message(
        self,
        raw: str,
        send_fn: Callable[[str], Awaitable[None]],
    ) -> NewsItem | None:
        """Procesa un frame JSON recibido desde Reverb."""
        try:
            frame = json.loads(raw)
        except ValueError:
            logger.debug("Ignored non-JSON WebSocket frame")
            return None

        if not isinstance(frame, dict):
            return None

        event_name = str(frame.get("event") or "")

        if event_name == "pusher:connection_established":
            await send_fn(
                json.dumps({"event": "pusher:subscribe", "data": {"channel": self.channel}})
            )
            return None

        if event_name == "pusher_internal:subscription_succeeded":
            self.is_connected = True
            self.last_error = None
            logger.info("Subscribed to public WebSocket channel '%s'", self.channel)
            await self.run_catchup()
            return None

        if event_name == "pusher:ping":
            await send_fn(json.dumps({"event": "pusher:pong", "data": {}}))
            return None

        if event_name == "pusher:error":
            self.last_error = str(frame.get("data") or "WebSocket protocol error")
            logger.warning("Error received from Reverb: %s", self.last_error)
            return None

        if event_name == "news.created":
            raw_data = frame.get("data")
            payload = (
                json.loads(raw_data)
                if isinstance(raw_data, str)
                else (raw_data if isinstance(raw_data, dict) else {})
            )
            item_dict = payload.get("item")
            if not isinstance(item_dict, dict):
                return None

            item = NewsItem.from_api_dict(item_dict)
            await self.on_item(item)
            await self.storage.set_last_item_id(item.id)
            self.last_event_at = datetime.now(UTC)
            return item

        return None

    async def run_catchup(self, max_pages: int = 10) -> int:
        """Recupera noticias nuevas perdidas durante desconexiones mediante since_id."""
        try:
            last_id = await self.storage.get_last_item_id()
            if last_id is None:
                # Primer arranque: fijar cursor sin reenviar el histórico completo
                latest = await self.api_client.get_items(order="desc", per_page=1)
                if latest:
                    await self.storage.set_last_item_id(latest[0].id)
                return 0

            processed = 0
            cursor = last_id
            for _ in range(max_pages):
                batch = await self.api_client.get_items(
                    since_id=cursor,
                    order="asc",
                    per_page=50,
                )
                if not batch:
                    break
                for item in batch:
                    await self.on_item(item)
                    await self.storage.set_last_item_id(item.id)
                    cursor = max(cursor, item.id)
                    self.last_event_at = datetime.now(UTC)
                    processed += 1
                if len(batch) < 50:
                    break

            return processed
        except WebApiUnavailableError as exc:
            logger.warning("Failed to complete initial catch-up: %s", exc)
            return 0

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        """Mantiene la conexión WebSocket activa con backoff exponencial hasta stop_event."""
        backoff = 1
        endpoint = self.build_ws_endpoint()

        while not stop_event.is_set():
            try:
                async with websockets.connect(
                    endpoint,
                    ping_interval=30,
                    ping_timeout=20,
                    open_timeout=10,
                ) as ws:
                    backoff = 1
                    while not stop_event.is_set():
                        recv_task = asyncio.create_task(ws.recv())
                        stop_task = asyncio.create_task(stop_event.wait())
                        done, pending = await asyncio.wait(
                            {recv_task, stop_task},
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        for task in pending:
                            task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await task

                        if stop_task in done:
                            break

                        raw = recv_task.result()
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        await self.handle_raw_message(raw, ws.send)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.is_connected = False
                self.last_error = str(exc)
                logger.warning("Reverb connection closed (%s). Retrying in %ss.", exc, backoff)
            finally:
                self.is_connected = False

            if stop_event.is_set():
                break

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=backoff)
            backoff = min(backoff * 2, 30)
