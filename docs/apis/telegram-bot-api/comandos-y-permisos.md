# Telegram Bot API — Dominio: Comandos y Permisos

- **Fuentes oficiales:** [`src/api.md`](./src/api.md) (`Determining list of commands`), [`src/setmycommands.md`](./src/setmycommands.md), [`src/botcommand.md`](./src/botcommand.md), [`src/getchatmember.md`](./src/getchatmember.md)
- **Fecha de descarga:** `2026-11-20`
- **Fecha de verificación real:** `2026-11-21` *(verificado en vivo `setMyCommands`/`getMyCommands` con los 11 comandos y `getChatMember` en supergrupo devolviendo `status=creator` aun siendo el bot `member`)*

---

## 1. Registro de comandos (`setMyCommands` y `BotCommand`)

### Método `setMyCommands` (`src/setmycommands.md`)

Actualiza el menú oficial de comandos visibles del bot y devuelve `true` si tuvo éxito.

| Parámetro | Tipo | Obligatorio | Descripción oficial |
|---|---|---|---|
| `commands` | `Array of BotCommand` | Sí | Lista JSON de hasta **100** comandos. |
| `scope` | `BotCommandScope` | Opcional | Ámbito de usuarios al que aplica (por defecto `BotCommandScopeDefault`). |
| `language_code` | `String` | Opcional | Código ISO 639-1 de 2 letras; si se omite aplica por defecto cuando no haya idioma específico. |

### Tipo `BotCommand` (`src/botcommand.md`)

| Campo | Tipo | Restricción oficial |
|---|---|---|
| `command` | `String` | **1–32 caracteres**; solo minúsculas inglesas (`a-z`), dígitos (`0-9`) y `_`. |
| `description` | `String` | **1–256 caracteres**. |
| `is_ephemeral` | `Boolean` | Opcional. Si es `true`, el comando envía un mensaje efímero visible solo para remitente y bot *(no usado aquí)*. |

### Orden de resolución de comandos (`src/api.md`)

- **En chat privado con el bot:** `ScopeChat + lang` → `ScopeChat` → `ScopeAllPrivateChats + lang` → `ScopeAllPrivateChats` → `ScopeDefault + lang` → `ScopeDefault`.
- **En grupos y supergrupos:** `ScopeChatMember (+ lang)` → `ScopeChatAdministrators (+ lang)` → `ScopeChat (+ lang)` → `ScopeAllChatAdministrators (+ lang)` → `ScopeAllGroupChats (+ lang)` → `ScopeDefault (+ lang)`.

---

## 2. Consulta de permisos (`getChatMember`)

### Método `getChatMember` (`src/getchatmember.md`)

Devuelve el objeto `ChatMember` con el rol y estado de un usuario concreto dentro de un chat.

| Parámetro | Tipo | Obligatorio | Descripción oficial |
|---|---|---|---|
| `chat_id` | `Integer` o `String` | Sí | ID numérico del chat o `@username` de supergrupo/canal. |
| `user_id` | `Integer` | Sí | Identificador numérico del usuario objetivo. |

### Requisito crítico y mapeo en `python-telegram-bot 22.8`

- **Garantía oficial:** Telegram solo garantiza que `getChatMember` funcione para consultar a terceros usuarios **si el bot es administrador del chat**.
- **Estados devueltos en la Bot API vs `telegram.constants.ChatMemberStatus` (verificado en entorno local `2026-11-20`):**
  - `"creator"` → `ChatMemberStatus.OWNER`
  - `"administrator"` → `ChatMemberStatus.ADMINISTRATOR`
  - `"member"` → `ChatMemberStatus.MEMBER`
  - `"restricted"` → `ChatMemberStatus.RESTRICTED`
  - `"left"` → `ChatMemberStatus.LEFT`
  - `"kicked"` → `ChatMemberStatus.BANNED`

> **Verificado (`2026-11-21`):** `setMyCommands` confirmó los 11 comandos y `getChatMember` devolvió `status=creator` en supergrupo real incluso con el bot como `member`.

---

> Creado: 2026-11-20 · Última revisión: 2026-11-21
