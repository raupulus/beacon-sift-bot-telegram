# Telegram Bot API — Dominio: Mensajería y Formato HTML

- **Fuentes oficiales:** [`src/sendmessage.md`](./src/sendmessage.md), [`src/formatting.md`](./src/formatting.md), [`src/linkpreviewoptions.md`](./src/linkpreviewoptions.md), [`src/responseparameters.md`](./src/responseparameters.md)
- **Fecha de descarga:** `2026-11-20`
- **Fecha de verificación real:** `2026-11-21` *(verificado en vivo `sendMessage` con `parse_mode=HTML`, entidades `&lt;`/`&gt;`/`&amp;`/`&#x27;` y `LinkPreviewOptions(is_disabled=True)` en supergrupo real; `message_thread_id` en foro `⚠️ sin verificar`)*

---

## 1. Método `sendMessage`

Envía mensajes de texto y devuelve en éxito el objeto `Message` enviado.

### Parámetros relevantes para este proyecto (`src/sendmessage.md`)

| Parámetro | Tipo | Obligatorio | Uso y notas oficiales |
|---|---|---|---|
| `chat_id` | `Integer` o `String` | Condicional | ID numérico del chat/supergrupo/canal o `@username` público (obligatorio salvo respuestas efímeras a *callback query*). |
| `message_thread_id` | `Integer` | Opcional | Identificador del hilo/*topic* en supergrupos foro (o chats privados de bots con modo foro habilitado). |
| `text` | `String` | Sí | Texto del mensaje: **1–4096 caracteres tras parsear entidades**. |
| `parse_mode` | `String` | Opcional | Modo de parseo de entidades (`"HTML"`, `"MarkdownV2"` o `"Markdown"` legado). |
| `link_preview_options` | `LinkPreviewOptions` | Opcional | Control de generación de vista previa de enlaces. |

---

## 2. `LinkPreviewOptions` (`src/linkpreviewoptions.md`)

| Campo | Tipo | Descripción oficial |
|---|---|---|
| `is_disabled` | `Boolean` | `true` para desactivar la vista previa del enlace. |
| `url` | `String` | URL explícita para la vista previa; si está vacío usa la primera URL del texto. |
| `prefer_small_media` | `Boolean` | Solicita miniatura reducida (si se especifica `url` y está soportado). |
| `prefer_large_media` | `Boolean` | Solicita miniatura ampliada (si se especifica `url` y está soportado). |
| `show_above_text` | `Boolean` | `true` para mostrar la vista previa encima del texto; si no, debajo. |

---

## 3. Formato `HTML` oficial (`src/formatting.md`)

Al pasar `parse_mode="HTML"`, Telegram acepta únicamente este subconjunto de etiquetas:

- **Énfasis:** `<b>`/`<strong>`, `<i>`/`<em>`, `<u>`/`<ins>`, `<s>`/`<strike>`/`<del>`
- **Spoiler:** `<span class="tg-spoiler">` o `<tg-spoiler>`
- **Enlaces y menciones:** `<a href="https://...">texto</a>`, `<a href="tg://user?id=123">mención</a>`
- **Código:** `<code>inline</code>`, `<pre>bloque</pre>`, `<pre><code class="language-python">...</code></pre>` *(no se puede poner clase de lenguaje en `<code>` suelto)*
- **Citas:** `<blockquote>...</blockquote>` y `<blockquote expandable>...</blockquote>`
- **Especiales:** `<tg-emoji emoji-id="...">👍</tg-emoji>` *(con restricciones de fragment/premium)* y `<tg-time unix="..." format="...">...</tg-time>`

### Reglas estrictas de escape HTML

1. Todo carácter `<`, `>` y `&` fuera de una etiqueta o entidad válida **debe** escaparse como `&lt;`, `&gt;` y `&amp;`.
2. Solo están soportadas **4 entidades nombradas**: `&lt;`, `&gt;`, `&amp;` y `&quot;`.
3. Todas las **entidades numéricas** (como `&#x27;` producida por `html.escape(..., quote=True)`) están soportadas.

---

## 4. Errores y control de flujo relevantes (`ResponseParameters`)

- **`429 Too Many Requests` (`parameters.retry_after`):** indica el número de segundos enteros a esperar antes de reintentar (en `python-telegram-bot` llega como excepción `RetryAfter` con `exc.retry_after`).
- **`403 Forbidden`:** bot bloqueado por usuario o expulsado/sin permisos de escritura en canal o grupo (`Forbidden` en `python-telegram-bot`).
- **`parameters.migrate_to_chat_id`:** cuando un grupo pasa a supergrupo, cambia a un ID de hasta 52 bits (`ChatMigrated`).

> **Verificado (`2026-11-21`):** `sendMessage` con `ParseMode.HTML`, `html.escape(..., quote=True)` (`&#x27;`) y `LinkPreviewOptions(is_disabled=True)` confirmado en supergrupo real; la entrega en *topics* con `message_thread_id` de foro queda `⚠️ sin verificar`.

---

> Creado: 2026-11-20 · Última revisión: 2026-11-21
