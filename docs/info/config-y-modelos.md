# Módulo `config-y-modelos`

> Ficheros cubiertos: [`src/config.py`](../../src/config.py), [`src/models.py`](../../src/models.py), [`.env.example`](../../.env.example)

## 1. Qué hace y qué NO hace

- **Hace:**
  - Lee y valida las variables de entorno del servicio desde `.env` / entorno mediante `pydantic-settings` (`Settings`).
  - Normaliza URLs base (eliminando barras finales) y el nivel de log (`upper()`).
  - Define la enumeración `Priority` (`low`, `medium`, `high`, `critical`) con peso ordenable, etiqueta en español e indicador visual.
  - Define DTOs inmutables (`frozen=True, slots=True`) para deserializar respuestas JSON de `web/` (`NewsItem`, `SourceSummary`, `SourceInfo`, `TypeInfo`, `ApiStatus`) y representar entidades locales (`ChatTarget`, `Subscription`).
- **NO hace:**
  - No realiza peticiones HTTP/WebSocket ni lecturas SQLite.
  - No aborta en construcción si falta `TELEGRAM_BOT_TOKEN` (eso se valida explícitamente en `main()`, permitiendo instanciar `Settings()` en tests unitarios sin token).

---

## 2. Modelo de datos

### `Priority` (`StrEnum` en `src/models.py`)

| Miembro | Valor | `weight` | `label_es` | `emoji` |
|---|---|---|---|---|
| `Priority.LOW` | `"low"` | `1` | `"Baja"` | `⚪` |
| `Priority.MEDIUM` | `"medium"` | `2` | `"Media"` | `🔵` |
| `Priority.HIGH` | `"high"` | `3` | `"Alta"` | `🟠` |
| `Priority.CRITICAL` | `"critical"` | `4` | `"Crítica"` | `🔴` |

### DTOs principales (`src/models.py`)

- `SourceSummary(slug, name, url)` — fuente embebida en una noticia. Si falta `name`, cae en `slug` o `"Fuente externa"`.
- `NewsItem(id, title, url, type, priority, priority_weight, published_at, fetched_at, snippet=None, image_url=None, author=None, tags=[], source=None)` — noticia/alerta normalizada (`type` en minúsculas; fechas ISO con soporte de sufijo `Z` y fallback `UTC` si llegan sin zona).
- `SourceInfo(slug, name, url, format, type, priority, interval_minutes, is_active, last_fetched_at=None, last_success_at=None, consecutive_failures=0)` — ítem devuelto por `/api/v1/sources`.
- `TypeInfo(type, sources_count, items_count)` — tipo devuelto por `/api/v1/types`.
- `ApiStatus(status, database, last_sync_at, sources_active, sources_failing, sources_total, items_total, ws_channel, ws_event)` — estado devuelto por `/api/v1/status`.
- `ChatTarget(chat_id, thread_id=0)` y `Subscription(chat_id, thread_id, source_type, min_priority, min_priority_weight)` — tipos internos usados entre `BotStorage` y el resto de módulos.

---

## 3. Flujos principales

1. Al instanciar `Settings()`, `BaseSettings` carga `.env` (`UTF-8`, `extra="ignore"`).
2. `@field_validator` limpia barras finales en `web_api_base_url` / `reverb_ws_url` y pasa `log_level` a mayúsculas.
3. Al recibir JSON de `web/`, `BeaconApiClient` y `ReverbListener` llaman a `*.from_api_dict(data)` y `_parse_iso_datetime()` normaliza timestamps con zona horaria garantizada (`tzinfo != None`).

---

## 4. Puntos de entrada (con auth, permisos y límites)

- `Settings`.
- `Priority.parse(value: str | None) -> Priority | None`.
- Métodos de factoría `from_api_dict(data)` en cada DTO (`ApiStatus`, `SourceInfo`, `TypeInfo`, `NewsItem`, `SourceSummary`).

> Sin validación de auth propia; `NewsItem.from_api_dict` requiere `data["id"]` convertible a `int` (lanza `KeyError` o `ValueError` si falta o no es entero).

---

## 5. Dependencias en ambos sentidos

- **Depende de:** `pydantic`, `pydantic-settings`, librería estándar (`dataclasses`, `datetime`, `enum`).
- **Consumido por:** prácticamente todos los módulos (`storage.py`, `api_client.py`, `reverb_client.py`, `formatter.py`, `permissions.py`, `dispatcher.py`, `handlers/*`, `main.py`).

---

## 6. Configuración (variables, valor por defecto y efecto)

Todas las variables están declaradas en [`src/config.py`](../../src/config.py) y ejemplificadas en [`.env.example`](../../.env.example):

| Variable (`.env`) | Atributo `Settings` | Valor por defecto | Efecto |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `telegram_bot_token` | `""` | Token de `@BotFather`; `main()` aborta con `exit(1)` si está vacío. |
| `ALLOW_PRIVATE_SUBSCRIPTIONS` | `allow_private_subscriptions` | `False` (`false`) | Si es `true`, cualquier usuario puede gestionar suscripciones en chat privado. |
| `TELEGRAM_DISABLE_WEB_PREVIEW` | `telegram_disable_web_preview` | `False` (`false`) | Activa (`false`) o desactiva (`true`) la previsualización web con imagen en alertas, `/latest` y `/search`. |
| `WEB_API_BASE_URL` | `web_api_base_url` | `"http://127.0.0.1:8000"` | URL base HTTP de `web/` (sin `/` final). |
| `WEB_API_TIMEOUT_SECONDS` | `web_api_timeout_seconds` | `10.0` | *Timeout* de peticiones `httpx` hacia `web/`. |
| `REVERB_WS_URL` | `reverb_ws_url` | `"ws://127.0.0.1:8080"` | URL base WebSocket (`ws://` o `wss://`) de Laravel Reverb. |
| `REVERB_APP_KEY` | `reverb_app_key` | `"beacon-sift-public-key"` | *App key* pública del servidor Reverb. |
| `REVERB_CHANNEL` | `reverb_channel` | `"beacon.news"` | Canal público WebSocket al que se suscribe el bot. |
| `BOT_DB_PATH` | `bot_db_path` | `"data/bot.db"` | Ruta al fichero SQLite (el `Dockerfile` sobrescribe por `ENV` a `/app/data/bot.db`). |
| `BOT_TIMEZONE` | `bot_timezone` | `"Europe/Madrid"` | Zona horaria IANA usada por `formatter.py` al renderizar fechas. |
| `LOG_LEVEL` | `log_level` | `"INFO"` | Nivel de logging estándar Python (`DEBUG`, `INFO`, `WARNING`, etc.). |

---

## 7. Trampas conocidas

- **`extra="ignore"`:** variables desconocidas en `.env` se ignoran silenciosamente.
- **Orden en `NewsItem.from_api_dict`:** si `priority` llega con valor desconocido desde la API, hace *fallback* silencioso a `Priority.LOW` (`priority_weight` toma el de la API si es `int`, o `priority.weight`).

---

## 8. Tests que lo cubren

- [`tests/test_main_and_config.py`](../../tests/test_main_and_config.py) — verifica normalización de URLs/`log_level` y `_parse_iso_datetime()`.
- [`tests/test_api_client.py`](../../tests/test_api_client.py) — ejercita `from_api_dict` de `ApiStatus`, `SourceInfo`, `TypeInfo`, `NewsItem` y `SourceSummary`.
- [`tests/test_dispatcher.py`](../../tests/test_dispatcher.py), [`tests/test_handlers.py`](../../tests/test_handlers.py), [`tests/test_formatter.py`](../../tests/test_formatter.py) — ejercitan `Settings`, `Priority` (`parse`, `weight`, `label_es`, `emoji`) y zona horaria.

---

## 9. Pendiente real

- Ninguno actualmente.

---

> Creado: 2026-11-20 · Última revisión: 2026-11-22
