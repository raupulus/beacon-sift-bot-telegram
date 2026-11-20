# Telegram Bot API — Dominio: Updates y Long Polling

- **Fuentes oficiales:** [`src/api.md`](./src/api.md) (`Getting updates`), [`src/getupdates.md`](./src/getupdates.md)
- **Fecha de descarga:** `2026-11-20`
- **Fecha de verificación real:** `2026-11-20` *(especificación descargada; flujo `getUpdates` en vivo `⚠️ sin verificar` por ausencia de `TELEGRAM_BOT_TOKEN` real)*

---

## 1. Método `getUpdates`

Recibe actualizaciones entrantes mediante *long polling* y devuelve un array de objetos `Update`.

### Parámetros oficiales (`src/getupdates.md`)

| Parámetro | Tipo | Obligatorio | Descripción oficial |
|---|---|---|---|
| `offset` | `Integer` | Opcional | Identificador del primer `Update` a devolver. Debe ser `max_update_id + 1` respecto a los ya recibidos para confirmarlos en el servidor. Un `offset` negativo recupera desde el final (`-offset`) y descarta anteriores. |
| `limit` | `Integer` | Opcional | Número máximo de actualizaciones por respuesta (`1` a `100`, defecto `100`). |
| `timeout` | `Integer` | Opcional | Espera de *long polling* en segundos. Defecto `0` (*short polling*, solo pruebas); en producción debe ser positivo. |
| `allowed_updates` | `Array of String` | Opcional | Lista JSON de tipos de `Update` deseados (ej. `["message", "edited_channel_post", "callback_query"]`). Array vacío recibe todos salvo `chat_member`, `message_reaction` y `message_reaction_count`. Si se omite, conserva la configuración previa. |

---

## 2. Reglas operativas verificadas en la documentación

1. **Confirmación de lectura:** una actualización se considera confirmada cuando se llama a `getUpdates` con un `offset` estrictamente mayor que su `update_id`. Recalcular siempre `offset` tras cada respuesta para evitar duplicados.
2. **Exclusividad:** `getUpdates` deja de funcionar mientras exista un webhook activo (requiere `deleteWebhook` previo para volver a polling).
3. **Caducidad en servidor:** Telegram retiene los `Update` no recogidos un máximo de **24 horas**.
4. **Cambio de `allowed_updates`:** no filtra retroactivamente actualizaciones encoladas antes de la llamada.

---

## 3. Qué tipos de `Update` interesan a `beacon-sift-bot-telegram`

En `src/main.py` se arranca `application.run_polling(allowed_updates=Update.ALL_TYPES)` para recibir comandos tanto desde:
- Chats privados, grupos y supergrupos (`Update.message` y mensajes editados según handlers).
- Canales de difusión donde administradores envían comandos directamente como publicaciones del canal (`Update.channel_post`, `Update.edited_channel_post`), contemplado explícitamente en `src/permissions.py` y `src/handlers/__init__.py`.

> **`⚠️ sin verificar` en vivo:** la recepción real de `channel_post` y `message_thread_id` desde servidores de Telegram queda pendiente de prueba con un token y canal reales.

---

> Creado: 2026-11-20 · Última revisión: 2026-11-20
