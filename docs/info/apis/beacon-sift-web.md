# Integración con `beacon-sift-web` (API v1 REST + Laravel Reverb)

- **Fuentes de código cubiertas:** [`src/api_client.py`](../../../src/api_client.py), [`src/reverb_client.py`](../../../src/reverb_client.py)
- **Servicio externo integrado:** `web/` (`https://feed.raupulus.dev` en producción, `http://127.0.0.1:8000` / `ws://127.0.0.1:8080` por defecto en local)
- **Fecha de verificación real:** `2026-11-20` *(verificada en vivo contra instancia local de `web/` con PostgreSQL + `php artisan serve` + `php artisan reverb:start` recibiendo eventos `news.created` y consultando `/api/v1/*`)*

---

## 1. Qué hace y qué NO hace

- **Hace:**
  - Consume exclusivamente los **4 endpoints públicos `GET` JSON** de `web/` (`/api/v1/status`, `/api/v1/sources`, `/api/v1/types`, `/api/v1/items`) mediante `BeaconApiClient` (`httpx.AsyncClient`).
  - Mantiene una conexión WebSocket persistente mediante protocolo **Pusher v7** contra Laravel Reverb (`ReverbListener`, librería `websockets`) escuchando el canal público configurado (`beacon.news`) y el evento `news.created`.
  - Ejecuta *catch-up* incremental por `since_id` al completar la suscripción al canal para recuperar noticias perdidas durante desconexiones.
- **NO hace:**
  - Nunca se conecta a PostgreSQL de `web/`, no autentica usuarios en `web/` ni escribe datos en el servicio web.
  - No realiza scraping de enlaces originales.

---

## 2. Contrato consumido de `web/`

### Endpoints REST (`src/api_client.py`)

Cabeceras enviadas: `Accept: application/json`, `User-Agent: beacon-sift-bot-telegram/0.1`.

| Método | Ruta y query params enviados | DTO devuelto | Notas reales |
|---|---|---|---|
| `get_status()` | `GET /api/v1/status` | `ApiStatus` | Lee `status`, `database`, `last_sync_at`, `sources.{active,failing,total}`, `items_total`, `websocket.{channel,event}`. |
| `get_sources(source_type, per_page)` | `GET /api/v1/sources?active=true&per_page=N[&type=...]` | `list[SourceInfo]` | `per_page` acotado a `1..100` (defecto `50`). |
| `get_types()` | `GET /api/v1/types` | `tuple[list[TypeInfo], list[Priority]]` | Si `priorities` viene vacío, usa fallback `list(Priority)`. |
| `get_items(...)` | `GET /api/v1/items?...` | `list[NewsItem]` | Soporta `type`, `min_priority`, `priority`, `source`, `q`, `since_id`, `order` (`asc`/`desc`), `per_page` (`1..50`). |

Todo error de red, timeout, HTTP >= 400, JSON inválido o payload raíz no `dict` registra `WARNING` en inglés (`Failed querying %s on web API: %s`) y lanza `WebApiUnavailableError`.

### Protocolo WebSocket Reverb / Pusher v7 (`src/reverb_client.py`)

- **URL construida (`build_ws_endpoint`):**
  `{reverb_ws_url}/app/{reverb_app_key}?protocol=7&client=beacon-telegram&version=1.0`
- **Eventos procesados en `handle_raw_message`:**
  1. `pusher:connection_established` → responde `{"event": "pusher:subscribe", "data": {"channel": self.channel}}`.
  2. `pusher_internal:subscription_succeeded` → marca `is_connected = True`, limpia `last_error`, registra `INFO` (`Subscribed to public WebSocket channel '%s'`) y lanza `await self.run_catchup()`.
  3. `pusher:ping` → responde `{"event": "pusher:pong", "data": {}}`.
  4. `pusher:error` → guarda `last_error` y registra `WARNING`.
  5. `news.created` → parsea `frame["data"]` (puede llegar serializado como `str` JSON o como `dict`), extrae `payload["item"]`, convierte a `NewsItem`, invoca `await self.on_item(item)`, avanza `last_processed_item_id` y actualiza `last_event_at`.

---

## 3. Flujo de *watermark*, *catch-up* y reconexión

1. **Primer arranque (`last_id is None`):** `run_catchup()` pide `get_items(order="desc", per_page=1)`, guarda el `id` más reciente en `bot_state` y devuelve `0` sin reenviar noticias antiguas.
2. **Reconexión (`last_id` presente):** pide hasta `max_pages=10` páginas de `50` ítems (`since_id=cursor, order="asc"`), llama a `on_item(item)` en orden cronológico y avanza `set_last_item_id(item.id)` tras cada ítem.
3. **Reintentos de `run_forever()`:** usa `websockets.connect(..., ping_interval=30, ping_timeout=20, open_timeout=10)` y *backoff* exponencial **`1s → 2s → 4s → 8s → 16s → 30s`** (resetea a `1s` al conectar). Vigila `stop_event` en paralelo a `ws.recv()`.

---

## 4. Configuración y trampas conocidas

| Variable (`.env`) | Atributo `Settings` | Valor por defecto | Efecto |
|---|---|---|---|
| `WEB_API_BASE_URL` | `web_api_base_url` | `"http://127.0.0.1:8000"` | URL base para `BeaconApiClient`. |
| `WEB_API_TIMEOUT_SECONDS` | `web_api_timeout_seconds` | `10.0` | Timeout HTTP de `httpx`. |
| `REVERB_WS_URL` | `reverb_ws_url` | `"ws://127.0.0.1:8080"` | URL base WebSocket (`ws://` o `wss://`). |
| `REVERB_APP_KEY` | `reverb_app_key` | `"beacon-sift-public-key"` | Clave pública de Reverb. |
| `REVERB_CHANNEL` | `reverb_channel` | `"beacon.news"` | Canal público de eventos. |

- **Trampa `data` string vs dict:** Laravel Reverb / Pusher envía el campo `data` de eventos de aplicación como una cadena JSON codificada doble; `handle_raw_message` contempla ambos formatos.
- **Límite del catch-up:** `max_pages=10` × `50` = **500 ítems** máximo por reconexión. Si el bot permaneciera offline acumulando más de 500 ítems nuevos, los excedentes esperarían a la siguiente reconexión o quedarían sin emitir hasta entonces.
- **Catch-up vs `set_last_item_id`:** en cada ítem de `news.created` o `run_catchup`, el cursor solo avanza **después** de `await self.on_item(item)`; si el proceso cae en medio, el ítem podrá re-procesarse protegido por `dispatched_items`.

---

## 5. Tests que lo cubren

- [`tests/test_api_client.py`](../../../tests/test_api_client.py) — prueba los 4 endpoints con `httpx.MockTransport` y el lanzamiento de `WebApiUnavailableError` ante HTTP `503`.
- [`tests/test_reverb_client.py`](../../../tests/test_reverb_client.py) — prueba handshake, suscripción, inicialización de *watermark* sin spam, `ping`/`pong`, evento `news.created` y *catch-up* incremental con `since_id`.

---

> Creado: 2026-11-20 · Última revisión: 2026-11-20
