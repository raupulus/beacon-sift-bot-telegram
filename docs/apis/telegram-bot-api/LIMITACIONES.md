# Telegram Bot API — Limitaciones y cuotas oficiales

- **Fuentes oficiales:** [`src/api.md`](./src/api.md), [`src/sendmessage.md`](./src/sendmessage.md), [`src/getupdates.md`](./src/getupdates.md), [`src/setmycommands.md`](./src/setmycommands.md), [`src/botcommand.md`](./src/botcommand.md), [`src/faq.md`](./src/faq.md)
- **Fecha de descarga:** `2026-11-20`
- **Fecha de verificación real:** `2026-11-21` *(límites verificados en documentación oficial; métodos básicos comprobados en vivo; comportamiento en vivo ante `429` bajo carga real `⚠️ sin verificar`)*

---

## 1. Límites de longitud y tamaño de payloads

| Recurso / Campo | Límite oficial | Notas y comportamiento en `bot-telegram/` |
|---|---|---|
| `sendMessage.text` | **1–4096 caracteres** *(tras parsear entidades)* | `src/formatter.py` acota conservadoramente a `TELEGRAM_SAFE_MAX_LENGTH = 4000` antes de enviar. |
| `setMyCommands.commands` | **Máximo 100 comandos** por ámbito/idioma | Actualmente se registran **11 comandos** del contrato. |
| `BotCommand.command` | **1–32 caracteres** (`a-z`, `0-9`, `_`) | Solo minúsculas inglesas, dígitos y guion bajo. |
| `BotCommand.description` | **1–256 caracteres** | Todas las descripciones de `BOT_COMMANDS` cumplen este rango. |
| Subida de ficheros por Bot API estándar | Fotos: 5 MB (URL) / 10 MB (`multipart`); otros: 20 MB (URL) / 50 MB (`multipart`) | No aplicable actualmente (el bot no envía adjuntos ni re-aloja imágenes). |

---

## 2. Límites de retención y polling (`getUpdates`)

- **Retención máxima en servidores de Telegram:** las actualizaciones entrantes no leídas se conservan como máximo **24 horas**.
- **`limit` por petición `getUpdates`:** entre **1 y 100** (valor por defecto `100`).
- **Exclusividad con webhooks:** `getUpdates` falla si el bot tiene configurado un webhook activo.

---

## 3. Límites de tasa (*Rate Limits / Flood Control*)

Según [`src/faq.md`](./src/faq.md) (`Broadcasting to Users`, límites gratuitos por defecto):

| Ámbito | Límite documentado por Telegram | Impacto si se supera |
|---|---|---|
| Chat individual | Evitar más de **1 mensaje/segundo** *(tolera ráfagas cortas)* | Error `429 Too Many Requests` con `ResponseParameters.retry_after`. |
| Grupo | Máximo **20 mensajes/minuto** | Error `429` (`RetryAfter` en `python-telegram-bot`). |
| Difusión masiva (*broadcast*) gratuita | ~**30 mensajes/segundo** globales | Error `429` salvo activar *paid broadcasts* (`allow_paid_broadcast`, hasta `1000 msg/s`, 0,1 Telegram Stars/msg, exige mínimo 100 000 Stars de saldo y 100 000 usuarios activos/mes). |

> **`⚠️ sin verificar` en producción:** los umbrales exactos bajo carga sostenida de este bot y los tiempos reales de `retry_after` devueltos por Telegram no han sido medidos en vivo para evitar provocar *flood bans* sobre el bot de pruebas.

---

## 4. Restricciones operativas en grupos, canales y *topics*

- **Canales:** los mensajes publicados en el canal llegan como `channel_post` / `edited_channel_post` **sin** objeto `effective_user` (o autoría delegada), y el bot debe ser administrador con permiso de publicar mensajes para enviar allí (`⚠️ sin verificar` en canal real).
- ***Topics* de foro (`message_thread_id`):** solo válido en supergrupos con modo foro activado o chats privados de bots con modo *forum topic* habilitado (`src/sendmessage.md`, `⚠️ sin verificar` en vivo).
- **Consulta de administradores (`getChatMember`):** solo garantizada en documentación oficial si el bot tiene rol de administrador en ese chat (`src/getchatmember.md`); en la verificación real del `2026-11-21` funcionó también con el bot como `member` en un supergrupo, pero conviene concederle rol de administrador en despliegues de producción.

---

> Creado: 2026-11-20 · Última revisión: 2026-11-21
