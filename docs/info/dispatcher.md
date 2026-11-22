# Módulo `dispatcher`

> Ficheros cubiertos: [`src/dispatcher.py`](../../src/dispatcher.py)

## 1. Qué hace y qué NO hace

- **Hace:**
  - Evalúa qué destinos `(chat_id, thread_id)` deben recibir una noticia `NewsItem` nueva según las suscripciones dinámicas configuradas en cada chat.
  - Reparte de forma concurrente y acotada (`max_concurrency=10`, cadencia global `min_interval_seconds=0.04` ≈ 25 msg/s) para escalar a cientos/miles de grupos sin que un `RetryAfter` en un chat bloquee el resto.
  - Evita envíos duplicados consultando y actualizando `dispatched_items` en `BotStorage`, y dispara poda periódica por antigüedad (`prune_dispatched(retention_days=30)`) cada `prune_every` entregas (por defecto `250`).
  - Formatea el mensaje HTML y aplica `LinkPreviewOptions(is_disabled=...)` y `message_thread_id` (cuando `thread_id > 0`).
  - Gestiona errores de Telegram por destino: migra automáticamente el `chat_id` en SQLite y reintenta ante `ChatMigrated`, espera y reintenta una vez ante `RetryAfter` (soportando `int`/`float` y `timedelta`), y auto-pausa el destino ante `Forbidden`.
- **NO hace:**
  - No realiza polling ni mantiene conexión WebSocket (recibe ítems vía *callback* desde `ReverbListener`).
  - No gestiona colas persistentes ni reintentos diferidos tras múltiples fallos consecutivos.

---

## 2. Modelo de datos

No define tablas propias; opera sobre `NewsItem` y `ChatTarget` de [`src/models.py`](../../src/models.py) y sobre `BotStorage`.

---

## 3. Flujos principales

1. `dispatch_item(item: NewsItem) -> int`:
   - Consulta `targets = await self.storage.get_matching_targets(item.type, item.priority_weight)` (solo destinos con `is_paused = 0` cuya suscripción coincida con `item.type` o `'all'` y `min_priority_weight <= item.priority_weight`).
   - Si no hay destinos, retorna `0` inmediatamente (sin formatear).
   - Renderiza `text = format_news_item(item, self.settings.bot_timezone)` una sola vez.
   - Lanza `_deliver_one(target)` concurrentemente con `asyncio.Semaphore(self.max_concurrency)` y regulación global `_acquire_rate_slot()`:
     - Si `await self.storage.was_dispatched(target.chat_id, target.thread_id, item.id)` → omite.
     - Llama a `_send_with_retry(...)`, que devuelve el `chat_id` efectivo entregado (`int | None`).
     - Si tuvo éxito (`sent_chat_id is not None`) → `await self.storage.mark_dispatched(sent_chat_id, target.thread_id, item.id)`.
   - Al finalizar el lote, acumula `delivered` y dispara `prune_dispatched(retention_days=self.prune_retention_days)` cada `prune_every` entregas.
2. `_send_with_retry(...)`:
   - Envía `bot.send_message(chat_id=..., text=..., parse_mode=ParseMode.HTML, link_preview_options=...)` añadiendo `message_thread_id=thread_id` solo si `thread_id > 0`.
   - **`ChatMigrated`:** registra `INFO`, ejecuta `await self.storage.migrate_chat_id(chat_id, exc.new_chat_id)` y reintenta el envío contra `exc.new_chat_id`.
   - **`RetryAfter`:** convierte `exc.retry_after` (`float` o `timedelta.total_seconds()`), acota a `[0.1, 15.0]` s, registra `WARNING`, duerme y reintenta una vez.
   - **`Forbidden`:** registra `WARNING` y llama a `await self.storage.set_paused(chat_id, thread_id, True)`.
   - **`TelegramError`:** registra `WARNING` y retorna `None`.

---

## 4. Puntos de entrada (con auth, permisos y límites)

- `AlertDispatcher(bot, storage, settings, *, prune_every=250, prune_retention_days=30, max_concurrency=10, min_interval_seconds=0.04)`
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
| `TELEGRAM_DISABLE_WEB_PREVIEW` | `telegram_disable_web_preview` | `False` | Configura `LinkPreviewOptions(is_disabled=...)` en cada alerta enviada (con `False` Telegram muestra imagen/tarjeta del enlace). |
| `BOT_TIMEZONE` | `bot_timezone` | `"Europe/Madrid"` | Zona horaria pasada a `format_news_item()`. |

---

## 7. Trampas conocidas

- **Desfase cuando `retry_after > 15s`:** al limitar la espera a 15 s, si Telegram exige un `retry_after` mayor (ej. 30 s) el reintento volverá a fallar y la alerta no se reintentará automáticamente (`⚠️ sin verificar` bajo carga real).
- **Envío real a Telegram:** `sendMessage` con `ParseMode.HTML` y `LinkPreviewOptions(is_disabled=True)` verificado en vivo el `2026-11-21` en supergrupo real; `message_thread_id`, `channel_post` y `RetryAfter`/`Forbidden` reales en producción siguen `⚠️ sin verificar`.

---

## 8. Tests que lo cubren

- [`tests/test_dispatcher.py`](../../tests/test_dispatcher.py):
  - `test_dispatcher_delivers_with_thread_id_dedups_and_pauses_on_forbidden`: filtrado por prioridad, `message_thread_id=42`, `LinkPreviewOptions(is_disabled=True)`, auto-pausa tras `Forbidden` y deduplicación.
  - `test_dispatcher_handles_retry_after_and_dynamic_types_per_chat`: reintento exitoso/fallido de `RetryAfter` y aislamiento por tipos dinámicos por grupo.
  - `test_dispatcher_migrates_chat_id_and_prunes_periodically`: migración automática ante `ChatMigrated` y disparo de `prune_dispatched()`.
  - `test_dispatcher_logs_generic_telegram_error_without_crashing`: resiliencia ante `TelegramError` genérico.

---

## 9. Pendiente real

- Validar en producción el comportamiento bajo carga con cientos/miles de grupos simultáneos (`⚠️ sin verificar` en vivo).

---

> Creado: 2026-11-20 · Última revisión: 2026-11-21
