# Telegram Bot API — Documentación destilada de terceros

- **Fuentes oficiales descargadas:** [`src/api.md`](./src/api.md), [`src/formatting.md`](./src/formatting.md), [`src/faq.md`](./src/faq.md), [`src/getupdates.md`](./src/getupdates.md), [`src/sendmessage.md`](./src/sendmessage.md), [`src/setmycommands.md`](./src/setmycommands.md), [`src/getchatmember.md`](./src/getchatmember.md), [`src/botcommand.md`](./src/botcommand.md), [`src/linkpreviewoptions.md`](./src/linkpreviewoptions.md), [`src/responseparameters.md`](./src/responseparameters.md) (origen: `https://core.telegram.org/bots/...` y changelog oficial `Bot API 10.4` del `2026-11-09`)
- **Fecha de descarga de fuentes:** `2026-11-20`
- **Fecha de verificación real:** `2026-11-21` *(verificados en vivo contra `https://api.telegram.org`: `getMe`, `getWebhookInfo`, `getUpdates` con `Update.ALL_TYPES`, `setMyCommands`/`getMyCommands`, `sendMessage` con `ParseMode.HTML` + `LinkPreviewOptions(is_disabled=True)` y `getChatMember` en supergrupo; ver tabla inferior)*
- **Cliente usado por el servicio:** `python-telegram-bot 22.8` (soporte declarado para Bot API `10.0`)

---

## Orden obligatorio de lectura dirigida

Al trabajar sobre la integración con Telegram, lee estos documentos en el orden siguiente:

1. [`README.md`](./README.md) *(este índice y estado de verificación)*
2. [`00-fundamentos.md`](./00-fundamentos.md) + [`ERRATAS.md`](./ERRATAS.md) + [`LIMITACIONES.md`](./LIMITACIONES.md)
3. **Solo** el dominio concreto que necesites:
   - [`updates-y-polling.md`](./updates-y-polling.md) — `getUpdates`, *long polling*, *offset* y `allowed_updates`
   - [`mensajeria-y-formato.md`](./mensajeria-y-formato.md) — `sendMessage`, `message_thread_id`, `LinkPreviewOptions`, `ParseMode.HTML` y `ResponseParameters`
   - [`comandos-y-permisos.md`](./comandos-y-permisos.md) — `setMyCommands`, `BotCommand`, resolución de *scopes* y `getChatMember`

> **Nota sobre `src/`:** el subdirectorio [`src/`](./src/) almacena las copias originales descargadas desde `core.telegram.org`. No se editan manualmente y no deben leerse de rutina; se consultan únicamente cuando se actualiza o audita esta destilación.

---

## Cómo integramos esta API en el proyecto

La configuración concreta de este bot, qué módulos invocan cada método y cómo mapeamos excepciones está documentado en [`docs/info/apis/telegram-bot-api.md`](../../info/apis/telegram-bot-api.md).

---

## Estado de verificación real (Regla 11)

| Aspecto | Estado | Evidencia / Nota |
|---|---|---|
| Endpoint HTTPS `https://api.telegram.org/bot<token>/METHOD_NAME` y error `401` | ✅ Verificado (`2026-11-20`) | Petición HTTPS real `401 Unauthorized: invalid token specified` |
| `getMe` y `getWebhookInfo` con token real | ✅ Verificado (`2026-11-21`) | Bot activo (`can_join_groups=True`, `can_read_all_group_messages=False`, sin webhook previo) |
| `getUpdates` (*long polling*, `Update.ALL_TYPES`) | ✅ Verificado (`2026-11-21`) | Recepción real de updates de supergrupo sin conflicto `409` |
| `setMyCommands` + `getMyCommands` (11 comandos) | ✅ Verificado (`2026-11-21`) | Telegram confirmó `ok=True` y devolvió exactamente los 11 comandos |
| `sendMessage` (`ParseMode.HTML`, `&#x27;`/`&lt;`/`&amp;`, `LinkPreviewOptions(is_disabled=True)`) | ✅ Verificado (`2026-11-21`) | Envío real en supergrupo con entidades `BOLD`, `CODE`, `TEXT_LINK`, `ITALIC` y preview desactivada |
| `getChatMember` en supergrupo | ✅ Verificado (`2026-11-21`) | Funcionó incluso con el bot en rol `member`, devolviendo `status=creator` |
| `channel_post` en canal y `message_thread_id` en supergrupo foro | `⚠️ sin verificar` | Pendiente de prueba en vivo en canal de difusión y supergrupo foro |
| Respuestas reales `429 RetryAfter`, `403 Forbidden` y `ChatMigrated` | `⚠️ sin verificar` | Cubierto con tests automatizados en `tests/test_dispatcher.py` |

---

> Creado: 2026-11-20 · Última revisión: 2026-11-21
