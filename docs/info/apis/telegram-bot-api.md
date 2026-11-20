# Integración con Telegram Bot API

- **Cliente usado:** `python-telegram-bot 22.8` (soporte Bot API `10.0`)
- **Documentación oficial destilada (terceros):** [`docs/apis/telegram-bot-api/README.md`](../../apis/telegram-bot-api/README.md)
- **Fecha de descarga de especificación oficial:** `2026-11-20`
- **Fecha de verificación real:** `2026-11-20` *(verificado acceso HTTPS y formato JSON `401` contra `https://api.telegram.org`; llamadas autenticadas `⚠️ sin verificar` al no existir `TELEGRAM_BOT_TOKEN` real en el entorno)*

> Este documento describe **únicamente cómo usa nuestro bot la API de Telegram** y qué módulos la llaman. La especificación, límites y erratas oficiales residen en [`docs/apis/telegram-bot-api/`](../../apis/telegram-bot-api/README.md) para no duplicar datos oficiales.

---

## 1. Métodos de la Bot API consumidos por el servicio

| Método Telegram Bot API | Dónde lo llamamos | Para qué y parámetros clave | Estado de verificación real |
|---|---|---|---|
| `getUpdates` (*long polling*) | [`src/main.py`](../../../src/main.py) (`application.run_polling(allowed_updates=Update.ALL_TYPES)`) | Recibe comandos desde privados, grupos, supergrupos/*topics* y `channel_post` en canales. | `⚠️ sin verificar` |
| `setMyCommands` | [`src/main.py`](../../../src/main.py) (`post_init` → `app.bot.set_my_commands(BOT_COMMANDS)`) | Registra en el menú de Telegram los 11 comandos de [`src/handlers/__init__.py`](../../../src/handlers/__init__.py) en ámbito por defecto. | `⚠️ sin verificar` |
| `sendMessage` | [`src/dispatcher.py`](../../../src/dispatcher.py) (`_send_with_retry`) y [`src/handlers/__init__.py`](../../../src/handlers/__init__.py) (`reply_html`) | Envía alertas y respuestas de comandos con `parse_mode=ParseMode.HTML`, `LinkPreviewOptions(is_disabled=...)` y `message_thread_id` (si `thread_id > 0`). | `⚠️ sin verificar` |
| `getChatMember` | [`src/permissions.py`](../../../src/permissions.py) (`can_manage_subscriptions`) | Verifica si el autor en grupos/supergrupos tiene rol `ADMINISTRATOR` u `OWNER`. | `⚠️ sin verificar` |

---

## 2. Convenciones de integración aplicadas en nuestro código

1. **Formato HTML unificado:** [`src/formatter.py`](../../../src/formatter.py) escapa entradas mediante `html.escape(text, quote=True)`, valida URLs `http`/`https` y limita la salida a `TELEGRAM_SAFE_MAX_LENGTH = 4000` (bajo el tope de 4096 descrito en [`LIMITACIONES.md`](../../apis/telegram-bot-api/LIMITACIONES.md)).
2. **Previsualización de enlaces controlada:** por defecto `TELEGRAM_DISABLE_WEB_PREVIEW=true` configura `LinkPreviewOptions(is_disabled=True)` tanto en alertas como en `/latest` y `/search` (en respuestas de sistema/ayuda `reply_html` desactiva siempre la vista previa por defecto).
3. **Soporte de *topics* y canales:**
   - `get_thread_id(update)` normaliza `message_thread_id` a `0` si no aplica.
   - `channel_post` / `edited_channel_post` habilita la gestión en canales sin requerir `effective_user`.
4. **Manejo de errores de plataforma en `AlertDispatcher`:**
   - `RetryAfter` → espera `min(max(retry_after, 0.1), 15.0)` segundos y reintenta una vez.
   - `Forbidden` → activa `is_paused = 1` en SQLite para ese `(chat_id, thread_id)`.
   - `TelegramError` → registra log `WARNING` en inglés sin abortar el resto de envíos.

---

## 3. Pendiente de verificación con token real (`⚠️ sin verificar`)

Cuando se disponga de un `TELEGRAM_BOT_TOKEN` de pruebas, validar en vivo y actualizar la cabecera de [`docs/apis/telegram-bot-api/README.md`](../../apis/telegram-bot-api/README.md):
- Registro visible del menú de los 11 comandos (`setMyCommands`).
- Envío HTML real de noticias largas y entidades `&#x27;` / `&amp;` / `&lt;`.
- Comandos ejecutados dentro de un **canal** (`channel_post`) y dentro de un ***topic* de supergrupo foro** (`message_thread_id > 0`).
- Comportamiento real de `getChatMember` con y sin rol administrador del bot en un grupo.

---

> Creado: 2026-11-20 · Última revisión: 2026-11-20
