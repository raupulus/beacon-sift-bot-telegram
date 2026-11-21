# Comandos del bot y de desarrollo (`commands.md`)

Referencia verificada directamente contra [`src/handlers/__init__.py`](../../src/handlers/__init__.py), [`src/handlers/info.py`](../../src/handlers/info.py), [`src/handlers/subscriptions.py`](../../src/handlers/subscriptions.py), [`pyproject.toml`](../../pyproject.toml) y [`docker-compose.yml`](../../docker-compose.yml).

---

## 1. Comandos de Telegram (`BOT_COMMANDS`)

Los **11 comandos** siguientes se registran en Telegram mediante `set_my_commands(BOT_COMMANDS)` dentro de `post_init` ([`src/main.py`](../../src/main.py)) y se enlazan con `CommandHandler` en `register_handlers()`, manteniendo paridad funcional exacta con el bot hermano `beacon-sift-bot-discord`.

### Comandos públicos de información y consulta

| Comando | Sintaxis | Permisos | Parámetros y límites reales | Comportamiento si API `web/` no responde |
|---|---|---|---|---|
| `/help` | `/help` | Todos | Ignora argumentos; devuelve la lista de 11 comandos en HTML (`format_help()`). | No requiere API `web/`. |
| `/status` | `/status` | Todos | Consulta `/api/v1/status` e incluye estado de `ReverbListener` (`is_connected`, `last_event_at`). | Muestra estado degradado (`API web: 🔴 No disponible en este momento`) sin fallar. |
| `/sources` | `/sources [type]` | Todos | Máximo 1 argumento (`args > 1` responde error de uso). Si se indica `type`, normaliza en minúsculas. | Responde `_API_UNAVAILABLE_MSG` en HTML. |
| `/types` | `/types` | Todos | Consulta `/api/v1/types`; lista tipos activos y niveles de prioridad (`low`, `medium`, `high`, `critical`). | Responde `_API_UNAVAILABLE_MSG` en HTML. |
| `/latest` | `/latest [type] [priority] [limit]` | Todos | `limit`: entero final (`[+-]?\d+`) en rango **`1..10`** (defecto `5`). Resto de tokens admite hasta 1 `priority` válida y 1 `type` en cualquier orden. | Responde `_API_UNAVAILABLE_MSG` en HTML. |
| `/search` | `/search <query> [type] [limit]` | Todos | Requiere `<query>` no vacía. Si `len(args) >= 2` y el último token es entero, se interpreta como `limit` (**`1..10`**, defecto `5`). Luego, si quedan `>= 2` tokens, consulta `/api/v1/types`: si el último token coincide con un tipo activo, lo usa como `[type]`. | Responde `_API_UNAVAILABLE_MSG` en HTML. |

### Comandos de gestión de suscripciones del canal

| Comando | Sintaxis | Permisos | Parámetros y validaciones reales | Efecto en SQLite (`data/bot.db`) |
|---|---|---|---|---|
| `/subscribe` | `/subscribe <type\|all> [min_priority]` | Admin (`can_manage_subscriptions`) | Exige 1 o 2 argumentos. `min_priority` por defecto **`low`** (válidos: `low`, `medium`, `high`, `critical`). Si `type != "all"`, valida contra `/api/v1/types`. | `UPSERT` en `chats` + `subscriptions` para `(chat_id, thread_id)`. |
| `/unsubscribe` | `/unsubscribe <type\|all>` | Admin (`can_manage_subscriptions`) | Exige exactamente 1 argumento. | Borra esa suscripción o todas (`all`) en `(chat_id, thread_id)`. |
| `/filters` | `/filters` | Todos en el chat/canal | Sin validación de permisos de admin; lista `list_subscriptions()` y `is_paused()`. | Solo lectura SQLite. |
| `/pause` | `/pause` | Admin (`can_manage_subscriptions`) | Sin argumentos requeridos. | Marca `is_paused = 1` en `chats` conservando los filtros en `subscriptions`. |
| `/resume` | `/resume` | Admin (`can_manage_subscriptions`) | Sin argumentos requeridos. | Marca `is_paused = 0` en `chats`. |

> **Trampa en `/search`:** como `[type]` se desambigua dinámicamente comparando el último token con `/api/v1/types` cuando hay al menos 2 palabras de búsqueda, una búsqueda como `/search kernel linux` toma `linux` como filtro `[type]` y busca solo `"kernel"` (documentado en [`handlers-y-arranque.md`](./handlers-y-arranque.md)).

> **Trampa en `/latest`:** aunque `BeaconApiClient.get_items` admite `per_page` hasta `50`, el comando público `/latest` y `/search` validan `1 <= limit <= 10` según el contrato.

### Contrato compartido de paridad y formato mínimo

Principios obligatorios compartidos entre `beacon-sift-bot-telegram` y `beacon-sift-bot-discord`:

1. **Paridad exacta de catálogo:** los 11 comandos mantienen los mismos nombres lógicos, semántica de filtros (`type`, `priority`, `query`, `limit` `1..10` con defecto `5`) y reglas de autorización. No deben existir comandos huérfanos en una sola plataforma salvo excepción documentada.
2. **Formato mínimo por noticia entregada:**
   - Titular enlazado directamente a la URL original (`http`/`https`).
   - Fuente (`source`), tipo (`type`) y prioridad (`priority`: `low`, `medium`, `high`, `critical`).
   - Fecha de publicación formateada (`BOT_TIMEZONE`).
   - Extracto breve (*snippet*) limpio y truncado bajo el límite seguro de Telegram (`TELEGRAM_SAFE_MAX_LENGTH = 4000` en `ParseMode.HTML`).
3. **Reglas unificadas de respuesta y errores:**
   - **Sin resultados:** responder claramente indicando que no hay elementos para los filtros aplicados.
   - **API `web/` no disponible:** responder con mensaje amigable (`_API_UNAVAILABLE_MSG` o estado degradado en `/status`) sin exponer trazas ni secretos, registrando el fallo en inglés en `logger.warning`.
   - **Parámetros inválidos:** indicar qué parámetro es incorrecto y mostrar el uso esperado del comando.

---

## 2. Comandos de desarrollo, calidad y ejecución local (`uv`)

Ejecutar siempre dentro de `bot-telegram/` (`uv` respeta `.python-version = 3.12`):

| Objetivo | Comando | Resultado esperado |
|---|---|---|
| Instalar / sincronizar entorno | `uv sync --python 3.12` | Crea/actualiza `.venv` con `uv.lock` y dependencias dev (`pytest`, `pytest-asyncio`, `ruff`). |
| Linter (Ruff) | `uv run ruff check src tests` | `All checks passed!` (reglas `E`, `F`, `I`, `UP`, `B`, `SIM`, máx. 100 columnas). |
| Verificación de formato | `uv run ruff format --check src tests` | `19 files already formatted` (o todos formateados). |
| Suite de tests | `uv run pytest` | `14 passed` (6 módulos de test en `tests/`, con `asyncio_mode = "auto"`). |
| Arrancar el bot en local | `uv run python -m src.main` | Lee `.env`, inicializa SQLite, conecta a Reverb y arranca `run_polling`. Aborta con código `1` si falta `TELEGRAM_BOT_TOKEN`. |

---

## 3. Comandos Docker / Docker Compose

| Objetivo | Comando | Notas |
|---|---|---|
| Construir imagen local | `docker build -t beacon-sift-bot-telegram .` | Imagen basada en `python:3.12-slim`, ejecuta como `botuser`. |
| Levantar servicio | `docker compose up -d --build` | Requiere `.env` en `bot-telegram/` y monta `./data:/app/data`. |
| Ver logs en vivo | `docker compose logs -f bot-telegram` | Logs estándar Python a `stdout`/`stderr`. |
| Parar servicio | `docker compose down` | Mantiene `./data/bot.db` en el host. |

Más detalles de despliegue en [`docs/deploys/docker.md`](../deploys/docker.md).

---

> Creado: 2026-11-20 · Última revisión: 2026-11-21
