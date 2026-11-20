"""Tests unitarios para BeaconApiClient usando httpx.MockTransport."""

from __future__ import annotations

import httpx
import pytest

from src.api_client import BeaconApiClient, WebApiUnavailableError
from src.models import Priority


async def test_api_client_parses_all_four_endpoints() -> None:
    captured_paths: list[tuple[str, dict[str, str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_paths.append((request.url.path, dict(request.url.params)))

        if request.url.path == "/api/v1/status":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "app": "beacon-sift",
                    "database": "ok",
                    "last_sync_at": "2026-11-20T15:00:00+01:00",
                    "sources": {"active": 3, "failing": 0, "total": 4},
                    "items_total": 42,
                    "websocket": {"channel": "beacon.news", "event": "news.created"},
                },
            )
        if request.url.path == "/api/v1/sources":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "slug": "debian-security",
                            "name": "Debian Security Advisories",
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
        if request.url.path == "/api/v1/types":
            return httpx.Response(
                200,
                json={
                    "types": [{"type": "cve", "sources_count": 2, "items_count": 30}],
                    "priorities": [
                        {"value": "low", "label": "Baja", "weight": 1},
                        {"value": "medium", "label": "Media", "weight": 2},
                        {"value": "high", "label": "Alta", "weight": 3},
                        {"value": "critical", "label": "Crítica", "weight": 4},
                    ],
                },
            )
        if request.url.path == "/api/v1/items":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 101,
                            "title": "DSA-6643-1 security update",
                            "url": "https://www.debian.org/security/2026/dsa-6643",
                            "snippet": "Security fix summary",
                            "type": "cve",
                            "priority": "high",
                            "priority_weight": 3,
                            "published_at": "2026-11-20T10:00:00+00:00",
                            "fetched_at": "2026-11-20T10:05:00+00:00",
                            "source": {
                                "slug": "debian-security",
                                "name": "Debian Security Advisories",
                                "url": "https://www.debian.org/security/dsa",
                            },
                        }
                    ]
                },
            )
        return httpx.Response(404)

    client = BeaconApiClient(
        "https://feed.raupulus.dev",
        transport=httpx.MockTransport(handler),
    )
    try:
        status = await client.get_status()
        assert status.status == "ok"
        assert status.sources_active == 3
        assert status.items_total == 42

        sources = await client.get_sources(source_type="CVE")
        assert len(sources) == 1
        assert sources[0].slug == "debian-security"
        assert sources[0].priority == Priority.HIGH

        types, priorities = await client.get_types()
        assert len(types) == 1
        assert types[0].type == "cve"
        assert [p.value for p in priorities] == ["low", "medium", "high", "critical"]

        items = await client.get_items(
            source_type="cve",
            min_priority=Priority.HIGH,
            query="DSA",
            since_id=50,
            order="asc",
            per_page=10,
        )
        assert len(items) == 1
        assert items[0].id == 101
        assert items[0].source is not None
        assert items[0].source.name == "Debian Security Advisories"
        assert captured_paths[-1][1]["min_priority"] == "high"
        assert captured_paths[-1][1]["since_id"] == "50"
    finally:
        await client.close()


async def test_api_client_raises_web_api_unavailable_on_errors() -> None:
    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "Service unavailable"})

    client = BeaconApiClient(
        "http://127.0.0.1:8000",
        transport=httpx.MockTransport(failing_handler),
    )
    try:
        with pytest.raises(WebApiUnavailableError):
            await client.get_status()
    finally:
        await client.close()
