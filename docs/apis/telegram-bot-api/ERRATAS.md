# Telegram Bot API — Erratas, matices y discrepancias conocidas

- **Fuentes oficiales:** [`src/api.md`](./src/api.md), [`src/formatting.md`](./src/formatting.md), [`src/getupdates.md`](./src/getupdates.md), [`src/getchatmember.md`](./src/getchatmember.md), [`src/responseparameters.md`](./src/responseparameters.md)
- **Fecha de descarga:** `2026-11-20`
- **Fecha de verificación real:** `2026-11-21` *(verificados en vivo `401`, `ParseMode.HTML` con `&#x27;`, `getChatMember` en supergrupo con bot como `member` y aviso `PTBDeprecationWarning` de `RetryAfter.retry_after`)*

---

## 1. Verificado mediante peticiones reales (`2026-11-20` / `2026-11-21`)

1. **Mensaje exacto de error `401` ante token inválido (`2026-11-20`):**
   - Una petición sin token válido (`GET https://api.telegram.org/bot000000:INVALID/getMe`) devuelve estado HTTP `401` con el payload `{"ok":false,"error_code":401,"description":"Unauthorized: invalid token specified"}`.
2. **Desfase entre Bot API publicada (`10.4`) y librería (`10.0`):**
   - Verificado en el entorno local (`telegram.__version__ == '22.8'`, `telegram.__bot_api_version__ == '10.0'`) frente al changelog oficial (`Bot API 10.4` del `2026-11-09`).
3. **Entidades HTML en `parse_mode=HTML` con `html.escape(..., quote=True)` (`2026-11-21`):**
   - Verificado en envío real a un supergrupo que Telegram acepta `&lt;`, `&gt;`, `&amp;` y la entidad numérica `&#x27;` generada por Python (`src/formatter.py`) sin errores de parseo. Siguen prohibidas entidades nombradas fuera de `&lt;`, `&gt;`, `&amp;`, `&quot;` (p. ej. `&apos;` o `&nbsp;`).
4. **`getChatMember` con bot en rol `member` en supergrupo (`2026-11-21`):**
   - Aunque la especificación oficial advierte que solo está garantizado si el bot es administrador del chat, en prueba real en supergrupo devolvió `status=creator` aun teniendo el bot rol `member`. Aun así, en producción conviene mantener al bot como administrador en grupos gestionados.
5. **Deprecación futura de `RetryAfter.retry_after` en `python-telegram-bot >= 22.2` (`2026-11-21`):**
   - Verificado al ejecutar `pytest`: `PTB` emitirá `datetime.timedelta` en futuras versiones mayores (`PTB_TIMEDELTA=1`). `src/dispatcher.py` soporta ambos tipos (`timedelta.total_seconds()` y `float`).
6. **`CommandHandler` ignora `channel_post` si no se especifican `filters` (`2026-11-22`):**
   - Verificado en `python-telegram-bot 22.8`: por defecto `CommandHandler` fija `filters=UpdateType.MESSAGES`, que devuelve `False` para `Update(channel_post=...)`. [`src/handlers/__init__.py`](../../../src/handlers/__init__.py) aplica `filters.UpdateType.MESSAGES | filters.UpdateType.CHANNEL_POSTS`.

---

## 2. Matices de la especificación pendientes de prueba en vivo (`⚠️ sin verificar`)

1. **`migrate_to_chat_id` supera 32 bits y cambia el `chat_id` del grupo (`src/responseparameters.md`):**
   - Cuando un grupo clásico se convierte en supergrupo, Telegram devuelve `migrate_to_chat_id` (hasta 52 bits) y `python-telegram-bot` lanza `ChatMigrated`. `src/dispatcher.py` y `src/storage.py` (`migrate_chat_id`) ya migran automáticamente suscripciones e historial (verificado en tests; `⚠️ sin verificar` en migración real de grupo).

2. **`getUpdates` + `allowed_updates` en transición (`src/getupdates.md`):**
   - Cambiar `allowed_updates` no afecta a actualizaciones generadas **antes** de la llamada a `getUpdates`, y si hubiera un webhook previo `getUpdates` fallaría hasta ejecutar `deleteWebhook`.

3. **Confirmación de `offset` negativo destructiva (`src/getupdates.md`):**
   - Pasar un `offset` negativo descarta actualizaciones pendientes anteriores en la cola del servidor (`run_polling` usa confirmación incremental estándar).

4. **`BotCommand.is_ephemeral` (`src/botcommand.md`):**
   - Los 11 comandos de `bot-telegram/` usan respuestas estándar públicas en el chat/canal.

---

> Creado: 2026-11-20 · Última revisión: 2026-11-22
