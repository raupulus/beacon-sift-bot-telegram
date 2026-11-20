# Módulo `dispatcher`

> Ficheros cubiertos: [`src/dispatcher.py`](../../src/dispatcher.py)

## 1. Qué hace y qué NO hace

- **Hace:**
  - Evalúa qué destinos `(chat_id, thread_id)` deben recibir una noticia `NewsItem` nueva.
  - Evita envíos duplicados consultando y actualizando `dispatched_items` en `BotStorage`.
  - Formatea el mensaje HTML y aplica `LinkPreviewOptions(is_disabled=...)` y `message_thread_id` (cuando `thread_id > 0`).
  - Gestiona errores de Telegram por destino: espera y reintenta una vez ante `RetryAfter`, y auto-pausa el destino ante `Forbidden`.
- **NO hace:**
  - No realiza polling ni mantiene conexión WebSocket (recibe ítems vía *callback* desde `ReverbListener`).
  - No gestiona colas persistentes ni reintentos diferidos tras múltiples fallos consecutivos.
  - No actualiza `chat_id` automáticamente ante `ChatMigrated` (`migrate_to_chat_id`).

---

## 2. Modelo de datos

No define tablas propias; opera sobre `NewsItem` y `ChatTarget` de [`src/models.py`](../../src/models.py) y sobre `BotStorage`.

---

## 3. Flujos principales

1. `dispatch_item(item: NewsItem) -> int`:
   - Consulta `targets = await self.storage.get_matching_targets(item.type, item.priority_weight)` (solo destinos con `is_paused = 0` cuya suscripción coincida con `item.type` o `'all'` y `min_priority_weight <= item.priority_weight`).
   - Si no hay destinos, retorna `0` inmediatamente (sin formatear).
   - Renderiza `text = format_news_item(item, self.settings.bot_timezone)` una sola vez.
   - Para cada `target`:
     - Si `await self.storage.was_dispatched(target.chat_id, target.thread_id, item.id)` → omite.
     - Llama a `_send_with_retry(...)`.
     - Si tuvo éxito (`True`) → `await self.storage.mark_dispatched(...)` e incrementa `delivered`.
2. `_send_with_retry(...)`:
   - Envía `bot.send_message(chat_id=..., text=..., parse_mode=ParseMode.HTML, link_preview_options=...)` añadiendo `message_thread_id=thread_id` solo si `thread_id > 0`.
   - **`RetryAfter`:** acota espera `wait_seconds = min(max(float(exc.retry_after), 0.1), 15.0)`, registra `WARNING`, duerme y reintenta una vez (si vuelve a fallar con `TelegramError`, registra `WARNING` y retorna `False`).
   - **`Forbidden`:** registra `WARNING` y llama a `await self.storage.set_paused(chat_id, thread_id, True)`.
   - **`TelegramError`:** registra `WARNING` y retorna `False`.

---

## 4. Puntos de entrada (con auth, permisos y límites)

- `AlertDispatcher(bot, storage, settings)`
- `async def dispatch_item(self, item: NewsItem) -> int` *(invocado como callback `on_item` por `ReverbListener`)*

Límites aplicados:
- Pausa máxima acotada por mensaje en `RetryAfter`: **`15.0` segundos** (1 solo reintento).

---

## 5. Dependencias en ambos sentidos

- **Depende de:** `python-telegram-bot` (`LinkPreviewOptions`, `ParseMode`, `Forbidden`, `RetryAfter`, `TelegramError`), [`src/config.py`](../../src/config.py), [`src/formatter.py`](../../src/formatter.py), [`src/models.py`](../../src/models.py), [`src/storage.py`](../../src/storage.py).
- **Consumido por:** [`src/main.py`](../../src/main.py) (se pasa `dispatcher.dispatch_item` como callback `on_item` a `ReverbListener`).

---

## 6. Configuración (variables, valor por defecto y efecto)

| Variable (`.env`) | Atributo `Settings` | Valor por defecto | Efecto |
|---|---|---|---|
| `TELEGRAM_DISABLE_WEB_PREVIEW` | `telegram_disable_web_preview` | `True` | Configura `LinkPreviewOptions(is_disabled=...)` en cada alerta enviada. |
| `BOT_TIMEZONE` | `bot_timezone` | `"Europe/Madrid"` | Zona horaria pasada a `format_news_item()`. |

---

## 7. Trampas conocidas

- **Desfase cuando `retry_after > 15s`:** al limitar la espera a 15 s, si Telegram exige un `retry_after` mayor (ej. 30 s) el reintento volverá a fallar y la alerta no se reintentará automáticamente (`⚠️ sin verificar` bajo carga real).
- **Bloqueo secuencial de bucle:** un `RetryAfter` en un destino bloquea la corrutina de `dispatch_item()` (y por tanto el bucle de recepción de `ReverbListener`) hasta 15 segundos para los destinos restantes de ese lote.
- **Migración a supergrupo (`ChatMigrated`):** si un grupo clásico pasa a supergrupo, Telegram devuelve error con `migrate_to_chat_id`; actualmente entra por `except TelegramError` sin migrar las suscripciones en SQLite ni auto-pausar.
- **Envío real a Telegram `⚠️ sin verificar`:** validado en tests con `FakeBot`; pendiente prueba con token y canal reales.

---

## 8. Tests que lo cubren

- [`tests/test_dispatcher.py`](../../tests/test_dispatcher.py):
  - `test_dispatcher_delivers_with_thread_id_dedups_and_pauses_on_forbidden`: verifica filtrado por prioridad, inclusión de `message_thread_id=42`, `LinkPreviewOptions(is_disabled=True)`, auto-pausa tras `Forbidden` y deduplicación al reenviar el mismo `item.id`.

---

## 9. Pendiente real

- Gestionar explícitamente `ChatMigrated` actualizando `(chat_id)` en SQLite.
- Añadir test para la rama `RetryAfter` y evaluar un limitador proactivo de cadencia (~20 msg/min por grupo / <30 msg/s global según [`LIMITACIONES.md`](../apis/telegram-bot-api/LIMITACIONES.md)) si crece el volumen de canales.

---

> Creado: 2026-11-20 · Última revisión: 2026-11-20
