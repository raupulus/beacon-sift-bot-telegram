# Telegram Bot API — Fundamentos

- **Fuentes oficiales:** [`src/api.md`](./src/api.md) (`Making requests`, `Available types`), changelog oficial `Bot API 10.4` (`2026-11-09`)
- **Fecha de descarga:** `2026-11-20`
- **Fecha de verificación real:** `2026-11-20` *(verificación HTTP sin token válido contra `api.telegram.org/bot.../getMe`)*

---

## 1. Esquema de peticiones y transporte

- **URL base estándar:** `https://api.telegram.org/bot<token>/METHOD_NAME` (obligatoriamente sobre HTTPS).
- **Métodos HTTP soportados:** `GET` y `POST`.
- **Nombres de método:** son *case-insensitive* (Telegram acepta indistintamente mayúsculas y minúsculas en `METHOD_NAME`).
- **Codificación:** todas las consultas deben enviarse en **UTF-8**.
- **Formas admitidas para pasar parámetros:**
  1. *URL query string*
  2. `application/x-www-form-urlencoded`
  3. `application/json` *(excepto al subir ficheros)*
  4. `multipart/form-data` *(obligatorio al subir ficheros)*

### Verificación real realizada (`2026-11-20`)

Petición directa ejecutada con `curl` contra `https://api.telegram.org/bot000000:INVALID/getMe`:
- Código HTTP devuelto: `401`
- Cuerpo JSON devuelto:
  ```json
  {"ok":false,"error_code":401,"description":"Unauthorized: invalid token specified"}
  ```
- Con esto queda verificado el envoltorio de error real en producción. El resto de métodos autenticados (`getUpdates`, `sendMessage`, `setMyCommands`, `getChatMember`) quedan `⚠️ sin verificar` hasta ejecutar contra un bot real con `TELEGRAM_BOT_TOKEN`.

---

## 2. Estructura de respuestas y errores

Según [`src/api.md`](./src/api.md), toda respuesta de la API devuelve un objeto JSON con:

| Campo | Tipo | Presencia | Significado |
|---|---|---|---|
| `ok` | `Boolean` | Siempre | `true` si la petición tuvo éxito; `false` en caso de error. |
| `result` | Objeto / Array / Primitivo | Solo si `ok == true` | Resultado concreto del método invocado. |
| `description` | `String` | Opcional (habitual si `ok == false`) | Descripción legible del resultado o del error. |
| `error_code` | `Integer` | Solo si `ok == false` | Código numérico orientativo (Telegram advierte que su contenido puede variar). |
| `parameters` | [`ResponseParameters`](./src/responseparameters.md) | Opcional en errores | Metadatos útiles para recuperación automática (`retry_after`, `migrate_to_chat_id`). |

### `ResponseParameters`

| Campo | Tipo | Descripción oficial |
|---|---|---|
| `migrate_to_chat_id` | `Integer` | Nuevo identificador cuando un grupo migra a supergrupo. Puede superar los 32 bits significativos (hasta 52 bits): requiere entero con signo de 64 bits o flotante doble. |
| `retry_after` | `Integer` | Segundos restantes que deben esperarse antes de reintentar tras superar el control de *flood* (`429`). |

---

## 3. Modelos de actualización y tipos de datos

- Los tipos de la API se serializan como objetos JSON y los campos marcados como *Optional* pueden omitirse en la respuesta cuando no son relevantes.
- Para campos `Integer` estándar basta con enteros con signo de 32 bits **salvo donde se indique expresamente** (como `chat_id` / `migrate_to_chat_id`, que pueden requerir 64 bits).
- Existen dos mecanismos mutuamente excluyentes para recibir actualizaciones (`Update`):
  - **`getUpdates`** (*long polling*, utilizado por este servicio).
  - **`setWebhook`** (webhooks salientes HTTPS).
- Un Bot API Server propio (`tdlib/telegram-bot-api`) es opcional para requisitos especiales (archivos > 50 MB, webhooks HTTP locales), innecesario en la arquitectura actual de este bot.

---

## 4. Relación entre la versión oficial y `python-telegram-bot`

- **Versión oficial documentada en `core.telegram.org` (`2026-11-20`):** `Bot API 10.4` (`2026-11-09`).
- **Versión de librería instalada (`uv.lock`):** `python-telegram-bot 22.8`, cuyo soporte declarado corresponde a `Bot API 10.0`.
- Ninguno de los métodos que usa actualmente `bot-telegram/` (`getUpdates`, `setMyCommands`, `sendMessage`, `getChatMember`) depende de novedades introducidas entre `10.1` y `10.4`, pero esta diferencia de versiones debe considerarse si en el futuro se incorporan *widgets* o parámetros recientes (`⚠️ sin verificar` en vivo).

---

> Creado: 2026-11-20 · Última revisión: 2026-11-20
