# Telegram Bot API — Documentación destilada de terceros

- **Fuentes oficiales descargadas:** [`src/api.md`](./src/api.md), [`src/formatting.md`](./src/formatting.md), [`src/faq.md`](./src/faq.md), [`src/getupdates.md`](./src/getupdates.md), [`src/sendmessage.md`](./src/sendmessage.md), [`src/setmycommands.md`](./src/setmycommands.md), [`src/getchatmember.md`](./src/getchatmember.md), [`src/botcommand.md`](./src/botcommand.md), [`src/linkpreviewoptions.md`](./src/linkpreviewoptions.md), [`src/responseparameters.md`](./src/responseparameters.md) (origen: `https://core.telegram.org/bots/...` y changelog oficial `Bot API 10.4` del `2026-11-09`)
- **Fecha de descarga de fuentes:** `2026-11-20`
- **Fecha de verificación real:** `2026-11-20` *(parcial: transporte HTTPS, estructura de respuesta JSON y error `401 Unauthorized` verificados contra `https://api.telegram.org`; los flujos autenticados quedan marcados como `⚠️ sin verificar` al no existir `TELEGRAM_BOT_TOKEN` real en el entorno)*
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
| Endpoint HTTPS `https://api.telegram.org/bot<token>/METHOD_NAME` | ✅ Verificado (`2026-11-20`) | Petición real HTTPS `GET .../getMe` con token inválido responde `HTTP 401` |
| Envoltorio JSON (`ok`, `error_code`, `description`) | ✅ Verificado (`2026-11-20`) | Respuesta real `{"ok":false,"error_code":401,"description":"Unauthorized: invalid token specified"}` |
| Especificación Markdown oficial descargada (`Bot API 10.4`) | ✅ Descargada (`2026-11-20`) | Snapshots íntegros en `src/` |
| `getUpdates` (*long polling*, `Update.ALL_TYPES`) | `⚠️ sin verificar` | Requiere `TELEGRAM_BOT_TOKEN` real contra `api.telegram.org` |
| `setMyCommands` (registro de 11 comandos) | `⚠️ sin verificar` | Requiere `TELEGRAM_BOT_TOKEN` real |
| `sendMessage` (`ParseMode.HTML`, `message_thread_id`, `link_preview_options`, `channel_post`) | `⚠️ sin verificar` | Requiere `TELEGRAM_BOT_TOKEN` real y chat/supergrupo/canal de prueba |
| `getChatMember` en grupos/supergrupos | `⚠️ sin verificar` | Requiere `TELEGRAM_BOT_TOKEN` real en grupo con y sin permisos de admin |
| Respuestas reales `429 RetryAfter` y `403 Forbidden` | `⚠️ sin verificar` | Cubierto solo mediante mocks en `tests/test_dispatcher.py` |

---

> Creado: 2026-11-20 · Última revisión: 2026-11-20
