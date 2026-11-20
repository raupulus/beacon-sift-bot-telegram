# Módulo `formatter`

> Ficheros cubiertos: [`src/formatter.py`](../../src/formatter.py)

## 1. Qué hace y qué NO hace

- **Hace:**
  - Genera todos los textos HTML seguros (`ParseMode.HTML`) enviados por el bot: alertas individuales (`format_news_item`), listados de `/latest` y `/search` (`format_news_list`), `/help`, `/status`, `/sources`, `/types` y `/filters`.
  - Escapa todo texto externo con `html.escape(text, quote=True)`.
  - Valida URLs con `safe_http_url()` admitiendo únicamente esquemas `http` y `https` con `netloc` no vacío.
  - Convierte fechas UTC/ISO a la zona horaria configurada (`Europe/Madrid` por defecto, con fallback a `UTC` si el nombre IANA no existe).
- **NO hace:**
  - No realiza llamadas de red ni envía mensajes a Telegram.
  - No genera `Markdown` ni `MarkdownV2`.

---

## 2. Modelo de datos

Constante pública:
- `TELEGRAM_SAFE_MAX_LENGTH = 4000` (margen conservador debajo del máximo oficial de 4096 caracteres de Telegram `sendMessage.text`).

No define clases propias; consume `ApiStatus`, `NewsItem`, `Priority`, `SourceInfo`, `Subscription`, `TypeInfo` de [`src/models.py`](../../src/models.py).

---

## 3. Flujos principales

1. **`format_news_item(item, timezone_name)`:**
   - Cabecera: `{emoji} <b>{PRIORIDAD_ES}</b> · <code>#{type}</code>`.
   - Titular: `<a href="{url}"><b>{title}</b></a>` si `safe_http_url(item.url)` es válida; si no, `<b>{title}</b>` sin enlace.
   - Extracto breve (`snippet`): colapsa espacios (`" ".join(text.split())`), calcula presupuesto `max(80, 4000 - base_len)` y lo recorta a `min(320, budget)` añadiendo `…` antes de escapar.
   - Pie: `<i>{source_name}</i> · {dd/mm/YYYY HH:MM}`.
   - Salvaguarda final: si la cadena completa supera `4000`, recorta a `message[:3999] + "…"`.
2. **`format_news_list(items, header, timezone_name)`:**
   - Itera numerando `1.`, `2.`, ... con título truncado a 160 chars y snippet opcional a 120 chars; detiene la adición de ítems antes de superar `4000` caracteres.
3. **Resto de helpers (`format_help`, `format_status`, `format_sources`, `format_types`, `format_filters`):** construyen bloques HTML compactos respetando `4000` caracteres en listados largos (`format_sources` añade aviso de truncado).

---

## 4. Puntos de entrada (con auth, permisos y límites)

Funciones públicas puras y síncronas:
- `escape_html(text)`
- `safe_http_url(url)`
- `format_datetime(dt, timezone_name="Europe/Madrid")`
- `format_news_item(item, timezone_name="Europe/Madrid")`
- `format_news_list(items, header, timezone_name="Europe/Madrid")`
- `format_help()`
- `format_status(api_status, ws_connected, last_event_at, timezone_name="Europe/Madrid")`
- `format_sources(sources, filter_type=None)`
- `format_types(types, priorities)`
- `format_filters(subscriptions, paused)`

---

## 5. Dependencias en ambos sentidos

- **Depende de:** librería estándar (`html`, `datetime`, `urllib.parse`, `zoneinfo`) y [`src/models.py`](../../src/models.py).
- **Consumido por:** [`src/dispatcher.py`](../../src/dispatcher.py), [`src/handlers/info.py`](../../src/handlers/info.py), [`src/handlers/subscriptions.py`](../../src/handlers/subscriptions.py).

---

## 6. Configuración (variables, valor por defecto y efecto)

| Variable (`.env`) | Atributo `Settings` | Valor por defecto | Efecto |
|---|---|---|---|
| `BOT_TIMEZONE` | `bot_timezone` | `"Europe/Madrid"` | Zona horaria aplicada en `format_datetime()`. Si es inválida en sistema, cae a `"UTC"`. |

---

## 7. Trampas conocidas

- **Recorte duro final en `format_news_item` (línea 82):** si un titular y su URL por sí solos superasen ~3900 caracteres, `message[:3999] + "…"` cortaría la cadena ya renderizada en HTML, pudiendo dejar abierta una etiqueta `<b>`/`<a>` o cortar una entidad `&amp;` (rechazable por Telegram). En la práctica los titulares de feeds reales son cortos, pero conviene truncar antes `title` igual que en `format_news_list`.
- **Entidades HTML en Telegram:** `html.escape(text, quote=True)` emite `&#x27;` para apóstrofos; es una entidad numérica soportada oficialmente según [`docs/apis/telegram-bot-api/ERRATAS.md`](../apis/telegram-bot-api/ERRATAS.md) (`⚠️ sin verificar` contra envío real con token).
- **`format_types` y `format_filters`:** no aplican el bucle de límite `4000` si hubiera decenas de tipos o suscripciones en un mismo chat.

---

## 8. Tests que lo cubren

- [`tests/test_formatter.py`](../../tests/test_formatter.py):
  - `test_format_news_item_escapes_html_and_respects_length_limit` (escape XSS `&lt;script&gt;`, `&amp;`, conversión horaria UTC → `Europe/Madrid` y límite `<= 4000`).
  - `test_format_news_item_ignores_unsafe_javascript_url` (rechazo de `javascript:alert(1)`).
  - `test_format_catalog_helpers` (cobertura de `format_help`, `format_status` con API disponible/indisponible, `format_sources`, `format_types`, `format_filters` y `format_news_list`).

---

## 9. Pendiente real

- Acotar la longitud máxima de `item.title` dentro de `format_news_item()` antes de generar etiquetas HTML para que el corte duro final nunca pueda seccionar un tag abierto.
- Verificar visualmente en un cliente real de Telegram con `TELEGRAM_BOT_TOKEN` (`⚠️ sin verificar`).

---

> Creado: 2026-11-20 · Última revisión: 2026-11-20
