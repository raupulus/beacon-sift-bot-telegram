# Módulo `storage`

> Ficheros cubiertos: [`src/storage.py`](../../src/storage.py)

## 1. Qué hace y qué NO hace

- **Hace:**
  - Gestiona de forma asíncrona la base de datos SQLite local del bot (`aiosqlite`) en modo `WAL` y con `foreign_keys=ON`.
  - Crea el directorio padre si `db_path != ":memory:"` y garantiza el esquema en `initialize()`.
  - Persiste chats/*topics* (`(chat_id, thread_id)`), estado de pausa (`is_paused`), reglas de suscripción (`source_type`, `min_priority`), deduplicación de alertas entregadas (`dispatched_items`) y el cursor global `last_processed_item_id`.
- **NO hace:**
  - No almacena artículos completos, fuentes ni credenciales de Telegram.
  - No accede ni replica datos de la base PostgreSQL de `web/`.
  - No gestiona hilos o cron propios (la poda `prune_dispatched()` es invocada por `main.py` al arranque y por `AlertDispatcher` periódicamente).

---

## 2. Modelo de datos

Esquema creado por `BotStorage.initialize()` ([`src/storage.py#L34-L74`](../../src/storage.py#L34-L74)):

| Tabla | Clave primaria | Columnas relevantes | Notas |
|---|---|---|---|
| `chats` | `(chat_id, thread_id)` | `title TEXT`, `is_paused INTEGER DEFAULT 0`, `created_at TEXT`, `updated_at TEXT` | `thread_id` vale `0` cuando no hay *topic* de foro. |
| `subscriptions` | `(chat_id, thread_id, source_type)` | `min_priority TEXT`, `min_priority_weight INTEGER`, `created_at TEXT` | `FOREIGN KEY (chat_id, thread_id) REFERENCES chats ON DELETE CASCADE`. |
| `bot_state` | `key TEXT` | `value TEXT` | Usa clave `'last_processed_item_id'` como *watermark* global. |
| `dispatched_items` | `(chat_id, thread_id, item_id)` | `dispatched_at TEXT` | Índice `idx_dispatched_at` sobre `(dispatched_at)`. |

---

## 3. Flujos principales

1. **Inicialización (`initialize()`):** crea carpeta si procede, abre conexión con `row_factory = aiosqlite.Row`, activa `WAL` y `foreign_keys=ON`, ejecuta `CREATE TABLE IF NOT EXISTS` y `commit()`.
2. **Suscripción (`subscribe()`):** normaliza `source_type` (`strip().lower()`), ejecuta `_ensure_chat` (haciendo *upsert* de `title` con `COALESCE`) e inserta o actualiza `min_priority` y `min_priority_weight` para `(chat_id, thread_id, source_type)`.
3. **Resolución de destinos (`get_matching_targets(item_type, priority_weight)`):** devuelve `SELECT DISTINCT s.chat_id, s.thread_id` uniendo `subscriptions` y `chats` donde `c.is_paused = 0`, `s.min_priority_weight <= priority_weight` y `s.source_type IN (item_type, 'all')`.
4. **Deduplicación (`was_dispatched` / `mark_dispatched`):** comprueba existencia de `(chat_id, thread_id, item_id)` antes de enviar y registra con `INSERT OR IGNORE` únicamente tras un envío exitoso.
5. **Cursor (`get_last_item_id` / `set_last_item_id`):** monotónico creciente; si `item_id <= current`, no retrocede ni modifica SQLite.

---

## 4. Puntos de entrada (con auth, permisos y límites)

Clase `BotStorage(db_path: str | Path)`:
- Ciclo de vida: `initialize()`, `close()`.
- Suscripciones y pausa: `subscribe()`, `unsubscribe()` (soporta `'all'` y devuelve `cursor.rowcount`), `list_subscriptions()` (ordena `'all'` primero y luego alfabéticamente), `set_paused()`, `is_paused()`, `get_matching_targets()`.
- Deduplicación y cursor: `was_dispatched()`, `mark_dispatched()`, `prune_dispatched(keep_last=5000)`, `get_last_item_id()`, `set_last_item_id()`, `migrate_chat_id(old_chat_id, new_chat_id)`.

> No implementa autorización propia; asume que los *handlers* ya validaron permisos antes de mutar estado.

---

## 5. Dependencias en ambos sentidos

- **Depende de:** `aiosqlite`, [`src/models.py`](../../src/models.py) (`ChatTarget`, `Priority`, `Subscription`), `pathlib`, `datetime`.
- **Consumido por:** [`src/main.py`](../../src/main.py), [`src/dispatcher.py`](../../src/dispatcher.py), [`src/reverb_client.py`](../../src/reverb_client.py), [`src/handlers/subscriptions.py`](../../src/handlers/subscriptions.py).

---

## 6. Configuración (variables, valor por defecto y efecto)

| Variable (`.env`) | Atributo `Settings` | Valor por defecto | Efecto |
|---|---|---|---|
| `BOT_DB_PATH` | `bot_db_path` | `"data/bot.db"` | Ruta donde `BotStorage` abre/crea el fichero SQLite (en Docker `Dockerfile` fija `/app/data/bot.db`). |

---

## 7. Trampas conocidas

- **Llamar antes de `initialize()`:** cualquier método privado `_db()` lanza `RuntimeError("BotStorage no inicializado; llama antes a initialize().")`.
- **Diferencia entre `subscribe()` y `unsubscribe()` con `'all'`:** `subscribe(..., 'all', ...)` guarda una regla explícita con `source_type = 'all'`; `unsubscribe(..., 'all')` elimina **todas** las filas del destino (tanto reglas específicas como la regla `'all'`).
- **No hay migraciones automáticas de esquema:** cambiar columnas en versiones futuras requerirá sentencias `ALTER TABLE` o migración explícita si ya existe `bot.db` en `./data`.

---

## 8. Tests que lo cubren

- [`tests/test_storage.py`](../../tests/test_storage.py):
  - `test_subscribe_update_and_unsubscribe` (alta, actualización de prioridad, borrado unitario y borrado masivo con `'all'`).
  - `test_matching_targets_respects_priority_pause_and_dedup` (filtrado por peso de prioridad, *topics* con `thread_id`, exclusión de chats pausados, deduplicación cuando coincide regla específica y `'all'`).
  - `test_dispatched_deduplication_and_watermark` (no retroceso del cursor, idempotencia de `mark_dispatched` y `prune_dispatched(keep_last=1)`).
  - `test_migrate_chat_id_transfers_subscriptions_pause_and_dispatched` (migración atómica de grupo clásico a supergrupo conservando *topics*, pausa y deduplicación).

---

## 9. Pendiente real

- Ninguno crítico actualmente (la poda periódica ya está conectada en `post_init` y `AlertDispatcher`, y `migrate_chat_id()` cubre migraciones a supergrupo).

---

> Creado: 2026-11-20 · Última revisión: 2026-11-21
