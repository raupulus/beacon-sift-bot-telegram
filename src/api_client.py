"""Cliente HTTP async de solo lectura para la API v1 de web/ (feed.raupulus.dev)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.models import ApiStatus, NewsItem, Priority, SourceInfo, TypeInfo

logger = logging.getLogger(__name__)


class WebApiUnavailableError(RuntimeError):
    """Error lanzado cuando la API de web/ no responde o devuelve una respuesta inválida."""


class BeaconApiClient:
    """Consume los 4 endpoints públicos GET JSON de web/ (/api/v1/*)."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout_seconds,
            transport=transport,
            headers={
                "Accept": "application/json",
                "User-Agent": "beacon-sift-bot-telegram/0.1",
            },
        )

    async def close(self) -> None:
        """Cierra el cliente HTTP subyacente."""
        await self._client.aclose()

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        try:
            response = await self._client.get(path, params=clean_params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Fallo consultando %s en web/: %s", path, exc)
            raise WebApiUnavailableError("No se pudo conectar con la API de beacon-sift.") from exc

        if not isinstance(payload, dict):
            raise WebApiUnavailableError("Respuesta JSON inesperada desde la API de beacon-sift.")

        return payload

    async def get_status(self) -> ApiStatus:
        """Consulta /api/v1/status."""
        data = await self._get_json("/api/v1/status")
        return ApiStatus.from_api_dict(data)

    async def get_sources(
        self,
        source_type: str | None = None,
        per_page: int = 50,
    ) -> list[SourceInfo]:
        """Consulta /api/v1/sources con filtro opcional por tipo."""
        data = await self._get_json(
            "/api/v1/sources",
            params={
                "type": source_type.strip().lower() if source_type else None,
                "active": "true",
                "per_page": max(1, min(per_page, 100)),
            },
        )
        raw_sources = data.get("data", [])
        if not isinstance(raw_sources, list):
            return []
        return [SourceInfo.from_api_dict(item) for item in raw_sources if isinstance(item, dict)]

    async def get_types(self) -> tuple[list[TypeInfo], list[Priority]]:
        """Consulta /api/v1/types devolviendo tipos activos y prioridades válidas."""
        data = await self._get_json("/api/v1/types")
        raw_types = data.get("types", [])
        types = (
            [TypeInfo.from_api_dict(entry) for entry in raw_types if isinstance(entry, dict)]
            if isinstance(raw_types, list)
            else []
        )

        raw_priorities = data.get("priorities", [])
        priorities: list[Priority] = []
        if isinstance(raw_priorities, list):
            for entry in raw_priorities:
                if isinstance(entry, dict):
                    parsed = Priority.parse(str(entry.get("value") or ""))
                    if parsed is not None:
                        priorities.append(parsed)

        if not priorities:
            priorities = list(Priority)

        return types, priorities

    async def get_items(
        self,
        *,
        source_type: str | None = None,
        min_priority: Priority | None = None,
        priority: Priority | None = None,
        source: str | None = None,
        query: str | None = None,
        since_id: int | None = None,
        order: str = "desc",
        per_page: int = 10,
    ) -> list[NewsItem]:
        """Consulta /api/v1/items con filtros compatibles con BOT_COMMANDS_CONTRACT.md."""
        data = await self._get_json(
            "/api/v1/items",
            params={
                "type": source_type.strip().lower() if source_type else None,
                "min_priority": min_priority.value if min_priority is not None else None,
                "priority": priority.value if priority is not None else None,
                "source": source.strip().lower() if source else None,
                "q": query.strip() if query else None,
                "since_id": since_id,
                "order": order,
                "per_page": max(1, min(per_page, 50)),
            },
        )
        raw_items = data.get("data", [])
        if not isinstance(raw_items, list):
            return []
        return [NewsItem.from_api_dict(entry) for entry in raw_items if isinstance(entry, dict)]
