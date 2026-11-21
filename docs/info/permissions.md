# Módulo `permissions`

> Ficheros cubiertos: [`src/permissions.py`](../../src/permissions.py)

## 1. Qué hace y qué NO hace

- **Hace:**
  - Determina de forma asíncrona si el emisor de un comando tiene permiso para modificar suscripciones o el estado de pausa del destino actual (`can_manage_subscriptions`).
- **NO hace:**
  - No persiste roles en base de datos local.
  - No gestiona permisos granulares por comando (aplica el mismo criterio a `/subscribe`, `/unsubscribe`, `/pause` y `/resume`).
  - No aplica restricciones a los comandos de consulta ni a `/filters`.

---

## 2. Modelo de datos

No define tablas ni modelos propios. Evalúa:
- `update.channel_post`, `update.edited_channel_post`, `update.effective_user`, `update.effective_chat` (`telegram.Update`).
- `Settings.allow_private_subscriptions`.
- `ChatMemberStatus.ADMINISTRATOR` y `ChatMemberStatus.OWNER` de `telegram.constants`.

---

## 3. Flujos principales

Orden estricto de evaluación en [`can_manage_subscriptions()`](../../src/permissions.py#L17-L56):

1. Si `update.channel_post is not None` o `update.edited_channel_post is not None` → devuelve **`True`** *(en canales de Telegram solo publican dueño y administradores del canal, aunque `effective_user` sea `None`)*.
2. Si `chat is None` → devuelve **`False`**.
3. Si `chat.type == ChatType.PRIVATE` → devuelve **`settings.allow_private_subscriptions`** (`False` por defecto).
4. Si `chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}` y `update.effective_message.sender_chat.id == chat.id` → devuelve **`True`** *(administrador anónimo publicando con identidad del propio grupo/supergrupo)*.
5. Si `user is None` → devuelve **`False`**.
6. Si `chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}`:
   - Llama a `await context.bot.get_chat_member(chat.id, user.id)`.
   - Ante `TelegramError`, registra log `WARNING` en inglés (`Failed to verify member %s in chat %s: %s`) y devuelve **`False`**.
   - Devuelve `True` solo si `member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}`.
7. Cualquier otro tipo de chat → **`False`**.

---

## 4. Puntos de entrada (con auth, permisos y límites)

- `async def can_manage_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE, settings: Settings) -> bool`

---

## 5. Dependencias en ambos sentidos

- **Depende de:** `python-telegram-bot` (`Update`, `ChatMemberStatus`, `ChatType`, `TelegramError`), [`src/config.py`](../../src/config.py), [`docs/apis/telegram-bot-api/comandos-y-permisos.md`](../apis/telegram-bot-api/comandos-y-permisos.md).
- **Consumido por:** [`src/handlers/subscriptions.py`](../../src/handlers/subscriptions.py).

---

## 6. Configuración (variables, valor por defecto y efecto)

| Variable (`.env`) | Atributo `Settings` | Valor por defecto | Efecto |
|---|---|---|---|
| `ALLOW_PRIVATE_SUBSCRIPTIONS` | `allow_private_subscriptions` | `False` | Permite (`true`) o deniega (`false`) configurar alertas en chat privado. En grupos y canales siempre gestionan sus propios dueños y administradores sin configuración manual en `.env`. |

---

## 7. Trampas conocidas

- **Requisito de `getChatMember` en Telegram:** según la especificación oficial ([`ERRATAS.md`](../apis/telegram-bot-api/ERRATAS.md)), Telegram solo garantiza consultar a terceros si el bot es administrador del chat. En prueba real del `2026-11-21` en un supergrupo funcionó incluso con el bot como `member` (devolviendo `status=creator`), pero en producción se recomienda otorgar rol administrador al bot en los grupos gestionados para evitar fallos futuros.
- **Canales sin `effective_user`:** los mensajes escritos en un canal llegan como `channel_post`; cualquier administrador con permiso de publicar en el canal puede configurar el bot en ese canal (`⚠️ sin verificar` en canal real).

---

## 8. Tests que lo cubren

- [`tests/test_permissions.py`](../../tests/test_permissions.py):
  - Administrador anónimo en supergrupo (`sender_chat.id == chat.id`) permitido; `sender_chat` ajeno denegado.
  - Fallo `TelegramError` en `get_chat_member()` deniega de forma segura.
  - Canales (`channel_post`), propietario de supergrupo (`OWNER`) y flag `allow_private_subscriptions`.
- [`tests/test_handlers.py`](../../tests/test_handlers.py) (`test_subscription_commands_permissions_and_lifecycle`):
  - Miembro normal en supergrupo, privado, `ADMINISTRATOR` y `channel_post`.

---

## 9. Pendiente real

- Verificar en vivo `channel_post` en un canal de difusión real y administrador anónimo en un supergrupo real (`⚠️ sin verificar`).

---

> Creado: 2026-11-20 · Última revisión: 2026-11-21
