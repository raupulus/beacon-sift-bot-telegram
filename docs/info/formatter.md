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

Constantes públicas:
- `TELEGRAM_SAFE_MAX_LENGTH = 4000` (margen conservador debajo del máximo oficial de 4096 caracteres de Telegram `sendMessage.text`).
- `MAX_ITEM_TITLE_LENGTH = 300` y `MAX_ITEM_URL_LENGTH = 2000` (acotan titular y URL antes de ensamblar etiquetas HTML).

No define clases propias; consume `ApiStatus`, `NewsItem`, `Priority`, `SourceInfo`, `Subscription`, `TypeInfo` de [`src/models.py`](../../src/models.py).

---

## 3. Flujos principales

1. **`format_news_item(item, timezone_name)`:**
   - Cabecera: `{emoji} <b>{PRIORIDAD_ES}</b> · <code>#{type}</code>` (truncando `type` a 64 chars).
   - Titular: truncado a `300` chars antes de escapar; envuelto en `<a href="{url}"><b>{title}</b></a>` si `safe_http_url(item.url)` es válida y `<= 2000` chars; si no, `<b>{title}</b>`.
   - Extracto breve (`snippet`): colapsa espacios, calcula presupuesto `4000 - base_len` y lo añade solo si `budget >= 40` (truncado a `min(320, budget)`).
   - Pie: `<i>{source_name}</i> · {dd/mm/YYYY HH:MM}` (`source_name` truncado a 120 chars).
   - Salvaguarda HTML segura: si superase `4000`, retira enlace/extracto antes de recortar texto plano, sin seccionar nunca etiquetas HTML abiertas.
2. **`format_news_list(items, header, timezone_name)`:**
   - Itera numerando `1.`, `2.`, ... con título truncado a 160 chars y snippet opcional a 120 chars; detiene la adición de ítems antes de superar `4000` caracteres.
3. **Resto de helpers (`format_help`, `format_status`, `format_sources`, `format_types`, `format_filters`):** todos los listados dinámicos (`format_sources`, `format_types`, `format_filters`) truncan de forma segura bajo `4000` caracteres añadiendo aviso de truncado.

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

- **Entidades HTML en Telegram:** `html.escape(text, quote=True)` emite `&lt;`, `&gt;`, `&amp;`, `&quot;` y `&#x27;`; verificado en vivo contra `sendMessage` (`ParseMode.HTML`) el `2026-11-21` confirmando parseo correcto de `BOLD`, `CODE`, `TEXT_LINK` e `ITALIC`.

---

## 8. Tests que lo cubren

- [`tests/test_formatter.py`](../../tests/test_formatter.py):
  - `test_format_news_item_escapes_html_and_respects_length_limit` (escape XSS `&lt;script&gt;`, `&amp;`, conversión horaria UTC → `Europe/Madrid` y límite `<= 4000`).
  - `test_format_news_item_ignores_unsafe_javascript_url` (rechazo de `javascript:alert(1)`).
  - `test_format_catalog_helpers` (cobertura de `format_help`, `format_status`, `format_sources`, `format_types`, `format_filters` y `format_news_list`).
  - `test_format_news_item_extreme_title_and_url_preserves_balanced_html` (titulares/URLs extremos manteniendo etiquetas HTML balanceadas y `<= 4000`).
  - `test_format_types_and_filters_truncate_under_telegram_limit` (150 tipos y 150 filtros bajo `4000` caracteres).

---

## 9. Pendiente real

- Ninguno crítico actualmente.

---

> Creado: 2026-11-20 · Última revisión: 2026-11-21
