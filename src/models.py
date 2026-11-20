"""Modelos y DTOs tipados compartidos en beacon-sift-bot-telegram."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Priority(StrEnum):
    """Niveles de prioridad alineados con web/ y BOT_COMMANDS_CONTRACT.md."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def weight(self) -> int:
        """Peso numérico ordenable para evaluar min_priority."""
        return {
            Priority.LOW: 1,
            Priority.MEDIUM: 2,
            Priority.HIGH: 3,
            Priority.CRITICAL: 4,
        }[self]

    @property
    def label_es(self) -> str:
        """Etiqueta legible en español."""
        return {
            Priority.LOW: "Baja",
            Priority.MEDIUM: "Media",
            Priority.HIGH: "Alta",
            Priority.CRITICAL: "Crítica",
        }[self]

    @property
    def emoji(self) -> str:
        """Indicador visual compacto para mensajes de Telegram."""
        return {
            Priority.LOW: "⚪",
            Priority.MEDIUM: "🔵",
            Priority.HIGH: "🟠",
            Priority.CRITICAL: "🔴",
        }[self]

    @classmethod
    def parse(cls, value: str | None) -> Priority | None:
        """Normaliza una prioridad textual o devuelve None si no es válida."""
        if value is None:
            return None
        clean = value.strip().lower()
        if not clean:
            return None
        try:
            return cls(clean)
        except ValueError:
            return None


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    normalized = raw.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(normalized)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class SourceSummary:
    """Resumen de la fuente asociada a una noticia."""

    slug: str
    name: str
    url: str

    @classmethod
    def from_api_dict(cls, data: dict[str, Any] | None) -> SourceSummary | None:
        if not isinstance(data, dict):
            return None
        slug = str(data.get("slug") or "").strip()
        name = str(data.get("name") or slug or "Fuente externa").strip()
        url = str(data.get("url") or "").strip()
        if not slug and not name:
            return None
        return cls(slug=slug, name=name, url=url)


@dataclass(frozen=True, slots=True)
class NewsItem:
    """Noticia o alerta normalizada recibida desde web/ (API v1 o Reverb)."""

    id: int
    title: str
    url: str
    type: str
    priority: Priority
    priority_weight: int
    published_at: datetime | None
    fetched_at: datetime | None
    snippet: str | None = None
    image_url: str | None = None
    author: str | None = None
    tags: list[str] = field(default_factory=list)
    source: SourceSummary | None = None

    @classmethod
    def from_api_dict(cls, data: dict[str, Any]) -> NewsItem:
        priority = Priority.parse(str(data.get("priority") or "low")) or Priority.LOW
        raw_weight = data.get("priority_weight")
        weight = int(raw_weight) if isinstance(raw_weight, int) else priority.weight
        raw_tags = data.get("tags")
        tags = [str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else []

        return cls(
            id=int(data["id"]),
            title=str(data.get("title") or "").strip(),
            url=str(data.get("url") or "").strip(),
            type=str(data.get("type") or "").strip().lower(),
            priority=priority,
            priority_weight=weight,
            published_at=_parse_iso_datetime(data.get("published_at")),
            fetched_at=_parse_iso_datetime(data.get("fetched_at")),
            snippet=(str(data["snippet"]).strip() if data.get("snippet") else None),
            image_url=(str(data["image_url"]).strip() if data.get("image_url") else None),
            author=(str(data["author"]).strip() if data.get("author") else None),
            tags=tags,
            source=SourceSummary.from_api_dict(data.get("source")),
        )


@dataclass(frozen=True, slots=True)
class SourceInfo:
    """Fuente activa devuelta por /api/v1/sources."""

    slug: str
    name: str
    url: str
    format: str
    type: str
    priority: Priority
    interval_minutes: int
    is_active: bool
    last_fetched_at: datetime | None = None
    last_success_at: datetime | None = None
    consecutive_failures: int = 0

    @classmethod
    def from_api_dict(cls, data: dict[str, Any]) -> SourceInfo:
        priority = Priority.parse(str(data.get("priority") or "medium")) or Priority.MEDIUM
        return cls(
            slug=str(data.get("slug") or ""),
            name=str(data.get("name") or ""),
            url=str(data.get("url") or ""),
            format=str(data.get("format") or "rss"),
            type=str(data.get("type") or ""),
            priority=priority,
            interval_minutes=int(data.get("interval_minutes") or 30),
            is_active=bool(data.get("is_active", True)),
            last_fetched_at=_parse_iso_datetime(data.get("last_fetched_at")),
            last_success_at=_parse_iso_datetime(data.get("last_success_at")),
            consecutive_failures=int(data.get("consecutive_failures") or 0),
        )


@dataclass(frozen=True, slots=True)
class TypeInfo:
    """Tipo de fuente activo devuelto por /api/v1/types."""

    type: str
    sources_count: int
    items_count: int

    @classmethod
    def from_api_dict(cls, data: dict[str, Any]) -> TypeInfo:
        return cls(
            type=str(data.get("type") or "").strip().lower(),
            sources_count=int(data.get("sources_count") or 0),
            items_count=int(data.get("items_count") or 0),
        )


@dataclass(frozen=True, slots=True)
class ApiStatus:
    """Estado general del servicio web devuelto por /api/v1/status."""

    status: str
    database: str
    last_sync_at: datetime | None
    sources_active: int
    sources_failing: int
    sources_total: int
    items_total: int
    ws_channel: str
    ws_event: str

    @classmethod
    def from_api_dict(cls, data: dict[str, Any]) -> ApiStatus:
        sources = data.get("sources") or {}
        ws = data.get("websocket") or {}
        return cls(
            status=str(data.get("status") or "unknown"),
            database=str(data.get("database") or "unknown"),
            last_sync_at=_parse_iso_datetime(data.get("last_sync_at")),
            sources_active=int(sources.get("active") or 0),
            sources_failing=int(sources.get("failing") or 0),
            sources_total=int(sources.get("total") or 0),
            items_total=int(data.get("items_total") or 0),
            ws_channel=str(ws.get("channel") or "beacon.news"),
            ws_event=str(ws.get("event") or "news.created"),
        )


@dataclass(frozen=True, slots=True)
class ChatTarget:
    """Destino único en Telegram (chat + topic opcional)."""

    chat_id: int
    thread_id: int = 0


@dataclass(frozen=True, slots=True)
class Subscription:
    """Regla de suscripción activa para un chat/topic."""

    chat_id: int
    thread_id: int
    source_type: str
    min_priority: Priority
    min_priority_weight: int
