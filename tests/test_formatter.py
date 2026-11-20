"""Tests unitarios para el formateador HTML de Telegram."""

from __future__ import annotations

from datetime import UTC, datetime

from src.formatter import (
    TELEGRAM_SAFE_MAX_LENGTH,
    format_filters,
    format_help,
    format_news_item,
    format_news_list,
    format_sources,
    format_status,
    format_types,
)
from src.models import (
    ApiStatus,
    NewsItem,
    Priority,
    SourceInfo,
    SourceSummary,
    Subscription,
    TypeInfo,
)


def test_format_news_item_escapes_html_and_respects_length_limit() -> None:
    huge_snippet = "<script>alert('xss')</script> & " + ("palabra " * 900)
    item = NewsItem(
        id=42,
        title="DSA <script> & Critical Advisory",
        url="https://www.debian.org/security/dsa-42?a=1&b=2",
        type="cve",
        priority=Priority.CRITICAL,
        priority_weight=4,
        published_at=datetime(2026, 11, 20, 14, 30, tzinfo=UTC),
        fetched_at=datetime(2026, 11, 20, 14, 31, tzinfo=UTC),
        snippet=huge_snippet,
        source=SourceSummary(slug="debian", name="Debian <Sec>", url="https://debian.org"),
    )

    rendered = format_news_item(item, "Europe/Madrid")

    assert len(rendered) <= TELEGRAM_SAFE_MAX_LENGTH
    assert "&lt;script&gt;" in rendered
    assert "&amp;" in rendered
    assert "🔴 <b>CRÍTICA</b>" in rendered
    assert "<code>#cve</code>" in rendered
    assert "20/11/2026 15:30" in rendered


def test_format_news_item_ignores_unsafe_javascript_url() -> None:
    item = NewsItem(
        id=1,
        title="Malicious link",
        url="javascript:alert(1)",
        type="news",
        priority=Priority.LOW,
        priority_weight=1,
        published_at=None,
        fetched_at=None,
    )

    rendered = format_news_item(item)
    assert "<a href=" not in rendered
    assert "<b>Malicious link</b>" in rendered


def test_format_catalog_helpers() -> None:
    help_text = format_help()
    assert "/subscribe" in help_text
    assert "/latest" in help_text

    status_ok = ApiStatus(
        status="ok",
        database="ok",
        last_sync_at=datetime(2026, 11, 20, 15, 0, tzinfo=UTC),
        sources_active=2,
        sources_failing=0,
        sources_total=3,
        items_total=40,
        ws_channel="beacon.news",
        ws_event="news.created",
    )
    assert "🟢 Conectado" in format_status(status_ok, True, None)
    assert "No disponible" in format_status(None, False, None)

    sources_text = format_sources(
        [
            SourceInfo(
                slug="debian-security",
                name="Debian Security",
                url="https://www.debian.org/security/dsa",
                format="rss",
                type="cve",
                priority=Priority.HIGH,
                interval_minutes=30,
                is_active=True,
            )
        ],
        "cve",
    )
    assert "Debian Security" in sources_text

    types_text = format_types(
        [TypeInfo(type="cve", sources_count=1, items_count=30)], list(Priority)
    )
    assert "cve" in types_text
    assert "critical" in types_text

    filters_text = format_filters(
        [
            Subscription(
                chat_id=-1001,
                thread_id=0,
                source_type="cve",
                min_priority=Priority.HIGH,
                min_priority_weight=3,
            )
        ],
        paused=False,
    )
    assert "Activo" in filters_text
    assert "high" in filters_text

    list_text = format_news_list(
        [
            NewsItem(
                id=5,
                title="Nota 1",
                url="https://example.org/5",
                type="linux",
                priority=Priority.MEDIUM,
                priority_weight=2,
                published_at=datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
                fetched_at=None,
                snippet="Extracto",
            )
        ],
        "Últimas noticias",
    )
    assert "Nota 1" in list_text
