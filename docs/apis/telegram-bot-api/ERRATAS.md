# Telegram Bot API — Erratas, matices y discrepancias conocidas

- **Fuentes oficiales:** [`src/api.md`](./src/api.md), [`src/formatting.md`](./src/formatting.md), [`src/getupdates.md`](./src/getupdates.md), [`src/getchatmember.md`](./src/getchatmember.md), [`src/responseparameters.md`](./src/responseparameters.md)
- **Fecha de descarga:** `2026-11-20`
- **Fecha de verificación real:** `2026-11-20` *(parcial; ver tabla de verificación)*

---

## 1. Verificado mediante petición real (`2026-11-20`)

1. **Mensaje exacto de error `401` ante token inválido:**
   - Una petición sin token válido (`GET https://api.telegram.org/bot000000:INVALID/getMe`) devuelve estado HTTP `401` con el payload `{"ok":false,"error_code":401,"description":"Unauthorized: invalid token specified"}`.
2. **Desfase entre Bot API publicada (`10.4`) y librería (`10.0`):**
   - Verificado en el entorno local (`telegram.__version__ == '22.8'`, `telegram.__bot_api_version__ == '10.0'`) frente al changelog oficial (`Bot API 10.4` del `2026-11-09`). Los parámetros nuevos posteriores a `10.0` (por ejemplo `sendWidget`) no existen como argumentos tipados en esta versión de `python-telegram-bot`.

---

## 2. Matices de la especificación con impacto directo en nuestro código (`⚠️ sin verificar` con token real)

1. **Entidades HTML restringidas en `parse_mode=HTML` (`src/formatting.md`):**
   - Telegram **solo admite cuatro entidades HTML nombradas**: `&lt;`, `&gt;`, `&amp;` y `&quot;`.
   - Adicionalmente admite entidades numéricas. La función `html.escape(text, quote=True)` de Python genera `&#x27;` para `'`, lo cual es entidad numérica válida, pero usar `html.unescape` parcial o entidades nombradas comunes de HTML5 como `&apos;` o `&nbsp;` provocaría error de parseo de Telegram (`⚠️ sin verificar` contra `sendMessage` real).
   - Solo son válidas las etiquetas explícitamente listadas por Telegram; cualquier etiqueta HTML no soportada o símbolo `<`, `>`, `&` sin escapar provoca rechazo del mensaje.

2. **`getChatMember` exige privilegios de administrador para otros usuarios (`src/getchatmember.md`):**
   - La documentación oficial advierte literalmente: *"The method is only guaranteed to work for other users if the bot is an administrator in the chat"*.
   - **Implicación real:** si añaden el bot a un grupo como miembro raso sin permiso de administrador, las llamadas a `/subscribe`, `/unsubscribe`, `/pause` o `/resume` realizadas por administradores del grupo pueden fallar al consultar `getChatMember` (capturado en `src/permissions.py` devolviendo denegación segura + log `WARNING`), salvo si el usuario figura en `TELEGRAM_ADMIN_IDS` (`⚠️ sin verificar` en grupo real).

3. **`migrate_to_chat_id` supera 32 bits y cambia el `chat_id` del grupo (`src/responseparameters.md`):**
   - Cuando un grupo clásico se convierte en supergrupo, Telegram devuelve `migrate_to_chat_id` (hasta 52 bits) y el identificador anterior deja de ser válido.
   - `python-telegram-bot` lanza `ChatMigrated`; actualmente `bot-telegram/` solo captura `Forbidden`, `RetryAfter` y `TelegramError` genérico, por lo que una migración a supergrupo requeriría volver a configurar filtros en el nuevo `chat_id` (`⚠️ sin verificar` en grupo real).

4. **`getUpdates` + `allowed_updates` en transición (`src/getupdates.md`):**
   - Cambiar `allowed_updates` no afecta a actualizaciones generadas **antes** de la llamada a `getUpdates`, por lo que pueden llegar actualizaciones no solicitadas durante un breve intervalo inicial.
   - Además, si en algún momento hubo un webhook registrado para ese token, `getUpdates` no funciona hasta eliminar el webhook (`deleteWebhook`).

5. **Confirmación de `offset` negativo destructiva (`src/getupdates.md`):**
   - Pasar un `offset` negativo a `getUpdates` descarta todas las actualizaciones pendientes anteriores en la cola del servidor. En producción se debe mantener siempre confirmación incremental (`run_polling` lo gestiona internamente, `⚠️ sin verificar` en vivo).

6. **`BotCommand.is_ephemeral` no soportado en `BOT_COMMANDS` actuales (`src/botcommand.md`):**
   - El campo `is_ephemeral` permite respuestas solo visibles para emisor y bot, introducido en revisiones recientes de la Bot API; los comandos de `bot-telegram/` no lo utilizan y usan mensajes públicos estándar en el canal.

---

> Creado: 2026-11-20 · Última revisión: 2026-11-20
