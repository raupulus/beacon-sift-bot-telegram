# Decisiones técnicas (`decisiones-tecnicas.md`)

Registro de decisiones deliberadas de arquitectura e implementación en `beacon-sift-bot-telegram` cuyo porqué conviene preservar para evitar regresiones o "correcciones" accidentales.

---

## 1. Persistencia local en SQLite WAL en lugar de acceso directo a PostgreSQL de `web/`

- **Decisión:** El bot almacena chats, suscripciones, *watermark* y deduplicación en SQLite local (`BOT_DB_PATH=data/bot.db` con `PRAGMA journal_mode=WAL;`) vía `aiosqlite`.
- **Motivo:** Regla estricta de aislamiento entre servicios de `beacon-sift`: `bot-telegram/` no debe compartir BD ni importar código de `web/`, sino consumir exclusivamente su API HTTP v1 pública y su WebSocket público. Permite desplegar el bot en un contenedor ligero sin credenciales ni acceso de red hacia PostgreSQL.
- **Consecuencia:** El bot es dueño exclusivo de su esquema en [`src/storage.py`](../../src/storage.py) y puede reconstruirse o migrarse sin coordinar migraciones con Laravel.

---

## 2. Clave compuesta `(chat_id, thread_id)` con `thread_id = 0` por defecto

- **Decisión:** Tanto `chats` como `subscriptions` y `dispatched_items` usan clave primaria compuesta que incluye `thread_id INTEGER NOT NULL DEFAULT 0`.
- **Motivo:** Telegram representa un chat normal (privado, grupo o canal) sin `message_thread_id`, mientras que un supergrupo con *topics* de foro asigna un `message_thread_id > 0` por hilo. Usar `0` como valor normalizado evita `NULL` en claves primarias SQLite (donde dos filas con `NULL` no colisionarían en `PRIMARY KEY` / `ON CONFLICT`).
- **Regla asociada:** En `AlertDispatcher._send_with_retry()`, `message_thread_id` solo se envía a Telegram si `thread_id > 0`.

---

## 3. *Watermark* inicial en primer arranque (`last_processed_item_id`)

- **Decisión:** Si `bot_state` no contiene `last_processed_item_id`, `ReverbListener.run_catchup()` consulta `/api/v1/items?order=desc&per_page=1`, guarda ese último `id` como cursor y devuelve `0` sin enviar alertas retroactivas.
- **Motivo:** Si un bot arranca por primera vez contra un `web/` que ya tiene cientos de noticias históricas, sin este *watermark* inicial el primer *catch-up* reenviaría todo el histórico en bloque a cualquier chat recién suscrito y dispararía errores `429 RetryAfter`.
- **Catch-up posterior:** En reconexiones sucesivas (`last_id` ya existe), consulta `since_id=cursor` en orden `asc` (hasta `max_pages=10` páginas de `50` ítems) para entregar solo las noticias nuevas emitidas mientras estuvo desconectado.

---

## 4. Auto-pausa ante `Forbidden` conservando filtros

- **Decisión:** Cuando `bot.send_message()` lanza `telegram.error.Forbidden` (bot expulsado del chat, bloqueado o sin permisos de escritura), `AlertDispatcher` llama a `storage.set_paused(chat_id, thread_id, True)` en lugar de ejecutar `DELETE` sobre `subscriptions`.
- **Motivo:** Evita reintentos inútiles en cada alerta nueva y, al mismo tiempo, si el administrador vuelve a invitar o dar permisos al bot y ejecuta `/resume`, recupera todas sus suscripciones configuradas sin perderlas.

---

## 5. Valores por defecto conservadores de privacidad y formato

- **`ALLOW_PRIVATE_SUBSCRIPTIONS=false`:** Por defecto los chats privados con el bot quedan bloqueados para `/subscribe`, `/unsubscribe`, `/pause` y `/resume`; en grupos y canales cada dueño o administrador gestiona su propia configuración de forma autónoma sin listas manuales en `.env`. Evita que terceros usen una instancia pública del bot como canal de notificaciones privadas sin autorización del operador.
- **`TELEGRAM_DISABLE_WEB_PREVIEW=false`:** Activa por defecto las tarjetas de vista previa nativa de enlaces de Telegram (`LinkPreviewOptions(is_disabled=False)`) en alertas automáticas, `/latest` y `/search` para mostrar miniaturas y *Vista Rápida* sin descargar ni re-alojar imágenes de prensa en el servidor propio (en mensajes de ayuda/estado del bot sigue desactivada).

---

## 6. Long polling (`run_polling`) frente a webhooks

- **Decisión:** [`src/main.py`](../../src/main.py) usa `application.run_polling(allowed_updates=Update.ALL_TYPES)` en lugar de configurar un webhook entrante.
- **Motivo:** Simplifica el despliegue como contenedor saliente (`docker compose up -d`) sin exigir dominio público, certificado TLS ni puerto HTTP expuesto dedicado al bot. Facilita además la convivencia en el mismo VPS junto a `web/` y `bot-discord/`.

---

## 7. `ParseMode.HTML` frente a `MarkdownV2`

- **Decisión:** Todo el formateo de salida en [`src/formatter.py`](../../src/formatter.py) genera `ParseMode.HTML` escapando datos no confiables con `html.escape(text, quote=True)`.
- **Motivo:** `MarkdownV2` exige escapar más de una docena de caracteres (`_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`) tanto en títulos como dentro de URLs, produciendo fallos frecuentes con titulares reales de feeds técnicos/CVE. `ParseMode.HTML` solo requiere escapar `<`, `>`, `&` y `"` (con entidad numérica `&#x27;` aceptada por Telegram).
- **Seguridad adicional:** Toda URL de enlace pasa antes por `safe_http_url()`, que rechaza esquemas distintos a `http` / `https` (como `javascript:` o `data:`).

---

## 8. Python `3.12` fijado y mensajes de log en inglés

- **Decisión de runtime:** Fijado Python `3.12` en [`.python-version`](../../.python-version), `requires-python = ">=3.12"` en [`pyproject.toml`](../../pyproject.toml) y `FROM python:3.12-slim` en [`Dockerfile`](../../Dockerfile) para asegurar paridad entre desarrollo con `uv` y contenedor Docker con ruedas compiladas estables.
- **Convención de idioma:** Documentación, comentarios, docstrings y textos visibles al usuario en Telegram van en **español**; identificadores, rutas y mensajes de log (`logger.*`) van en **inglés**.

---

> Creado: 2026-11-20 · Última revisión: 2026-11-21
