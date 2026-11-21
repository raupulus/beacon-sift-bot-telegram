# Módulo `handlers-y-arranque`

> Ficheros cubiertos: [`src/main.py`](../../src/main.py), [`src/handlers/__init__.py`](../../src/handlers/__init__.py), [`src/handlers/info.py`](../../src/handlers/info.py), [`src/handlers/subscriptions.py`](../../src/handlers/subscriptions.py)

## 1. Qué hace y qué NO hace

- **Hace:**
  - Configura logging y valida `TELEGRAM_BOT_TOKEN` al arrancar (`src/main.py`).
  - Construye la `Application` de `python-telegram-bot`, inicializa `BotStorage`, registra `BOT_COMMANDS` en Telegram (`set_my_commands`) y lanza `ReverbListener.run_forever()` en segundo plano en `post_init`.
  - Cierra ordenadamente el *listener*, `httpx.AsyncClient` y `BotStorage` en `post_shutdown`.
  - Expone los **11 comandos** definidos en `BOT_COMMANDS_CONTRACT.md` repartidos entre consultas públicas (`info.py`) y gestión de suscripciones (`subscriptions.py`).
- **NO hace:**
  - No expone servidor HTTP ni webhook propio; opera mediante `run_polling(allowed_updates=Update.ALL_TYPES)`.
  - No introduce comandos propios fuera de `BOT_COMMANDS_CONTRACT.md`.

---

## 2. Modelo de datos

En [`src/handlers/__init__.py`](../../src/handlers/__init__.py):
- `@dataclass(slots=True) class BotAppContext`: agrupa `settings`, `storage`, `api_client`, `dispatcher` y `reverb_listener` bajo `application.bot_data["app_ctx"]`.
- `BOT_COMMANDS: list[BotCommand]`: lista exacta de los 11 comandos declarados a Telegram.

---

## 3. Flujos principales

### Ciclo de vida (`src/main.py`)

1. `main()` lee `Settings()`, configura logging (`httpx` elevado a `WARNING`) y aborta (`sys.exit(1)`) si `telegram_bot_token` está vacío.
2. `build_application(settings)` crea `BotStorage`, `BeaconApiClient`, `Application` con hooks `post_init` / `post_shutdown`, `AlertDispatcher`, `ReverbListener`, guarda `BotAppContext` en `bot_data["app_ctx"]` y registra los 11 handlers (`register_handlers`).
3. `post_init(app)`:
   - `await storage.initialize()`
   - `await storage.prune_dispatched(keep_last=5000)`
   - `await app.bot.set_my_commands(BOT_COMMANDS)`
   - Arranca tarea `asyncio` `"reverb-listener"` con `stop_event`.
4. `post_shutdown(app)`: activa `stop_event`, cancela `"reverb-listener"`, cierra `api_client` y `storage`.

### Procesado de comandos (`src/handlers/`)

- **Consultas (`info.py`):** ver parámetros, rangos y fallbacks en [`commands.md`](./commands.md).
- **Suscripciones (`subscriptions.py`):** salvo `filters_command`, todos comprueban `can_manage_subscriptions()`, extraen `(chat.id, get_thread_id(update))` y operan sobre `BotStorage`. `subscribe_command` valida tipos distintos de `'all'` contra `/api/v1/types`.

---

## 4. Puntos de entrada (con auth, permisos y límites)

- CLI / contenedor: `python -m src.main` → `main()`.
- Factoría testeable: `build_application(settings: Settings) -> Application`.
- Helpers compartidos en `src/handlers/__init__.py`: `get_app_context()`, `get_thread_id()`, `reply_html()`, `register_handlers()`.
- Los 11 `CommandHandler`: detallados en [`commands.md`](./commands.md).

---

## 5. Dependencias en ambos sentidos

- **Depende de:** `python-telegram-bot` (`Application`, `CommandHandler`, `BotCommand`, `LinkPreviewOptions`, `Update`), y todos los módulos internos (`config`, `models`, `storage`, `api_client`, `reverb_client`, `formatter`, `permissions`, `dispatcher`).
- **Consumido por:** punto de entrada Docker (`Dockerfile`) y `tests/test_handlers.py`.

---

## 6. Configuración (variables, valor por defecto y efecto)

| Variable (`.env`) | Atributo `Settings` | Valor por defecto | Efecto |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `telegram_bot_token` | `""` | Token del bot; obligatorio para iniciar `main()`. |
| `LOG_LEVEL` | `log_level` | `"INFO"` | Nivel raíz de logging en `configure_logging()`. |
| `TELEGRAM_DISABLE_WEB_PREVIEW` | `telegram_disable_web_preview` | `True` | Controla vista previa de enlaces en `/latest` y `/search`. |
| `BOT_TIMEZONE` | `bot_timezone` | `"Europe/Madrid"` | Zona horaria mostrada en `/status`, `/latest` y `/search`. |

*(Usa además `TELEGRAM_ADMIN_IDS`, `ALLOW_PRIVATE_SUBSCRIPTIONS`, `WEB_API_*`, `REVERB_*` y `BOT_DB_PATH` al instanciar los componentes en `build_application`.)*

---

## 7. Trampas conocidas

- **Desambiguación de `[type]` en `/search <query> [type] [limit]` (`info.py` líneas 182–188):** si hay al menos dos palabras restantes tras extraer `limit`, consulta `/api/v1/types` y toma el último token como `source_type` si coincide con un tipo activo. Buscar literalmente `"kernel linux"` cuando `"linux"` es tipo activo filtrará por `#linux` buscando `"kernel"`.
- **`update.effective_chat` `None`:** en `subscriptions.py` (`subscribe`, `unsubscribe`, `filters`, `pause`, `resume`), si `chat is None` retornan silenciosamente sin responder.
- **`setMyCommands` y `getUpdates` verificados en vivo (`2026-11-21`):** confirmados los 11 comandos registrados y polling `Update.ALL_TYPES` contra `api.telegram.org`; quedan `⚠️ sin verificar` en vivo el flujo interactivo completo con `channel_post` y *topics* de supergrupo foro.

---

## 8. Tests que lo cubren

- [`tests/test_handlers.py`](../../tests/test_handlers.py):
  - `test_all_info_commands_and_validation` (`/help`, `/status`, `/sources`, `/types`, `/latest`, límite `1..10`, `/search` con tipo/sin resultados/sin args).
  - `test_info_commands_handle_unavailable_api` (`/status` degradado y `/latest` con API caída `503`).
  - `test_subscription_commands_permissions_and_lifecycle` (permisos grupo/privado/admin/`channel_post`, validación de tipo inexistente, `/subscribe`, `/pause`, `/filters`, `/resume`, `/unsubscribe`).
- [`tests/test_main_and_config.py`](../../tests/test_main_and_config.py):
  - `test_build_application_post_init_and_post_shutdown` (ciclo completo `build_application`, `post_init`, `set_my_commands(BOT_COMMANDS)` y cancelación de `reverb-listener` en `post_shutdown`).

---

## 9. Pendiente real

- Validar en vivo comandos interactivos en canal (`channel_post`) y en supergrupo con modo foro (*topics* `message_thread_id`) (`⚠️ sin verificar`).

---

> Creado: 2026-11-20 · Última revisión: 2026-11-21
