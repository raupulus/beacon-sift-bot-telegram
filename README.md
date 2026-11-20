<p align="left">
  <img src="./images/logo-512x512.png" alt="beacon-sift Telegram Bot" width="84" align="left" style="margin-right: 16px;">
  <h1>beacon-sift — Bot de Telegram</h1>
</p>

<br clear="left"/>

Servicio independiente en **Python + Docker** que distribuye en tiempo real hacia canales y grupos de **Telegram** las noticias técnicas, avisos locales y alertas CVE agregadas por [`feed.raupulus.dev`](https://feed.raupulus.dev).

---

## Objetivo del servicio

- Recibir alertas en vivo mediante **WebSockets públicos** (Laravel Reverb) y filtrarlas por canal/grupo según **tipo de fuente** (`type`) y **prioridad mínima** (`low`, `medium`, `high`, `critical`).
- Permitir consultas bajo demanda y administración de filtros mediante comandos de Telegram cumpliendo el contrato compartido `BOT_COMMANDS_CONTRACT.md`.
- Operar de forma **desacoplada** de la base de datos de `web/`, consumiendo únicamente el WebSocket público y los endpoints `GET` JSON de solo lectura (`/api/v1/status`, `/api/v1/sources`, `/api/v1/types`, `/api/v1/items`).

---

## Catálogo de comandos previstos

- **Consulta (públicos):** `/help`, `/status`, `/sources [type]`, `/types`, `/latest [type] [priority] [limit]`, `/search <query> [type] [limit]`
- **Gestión de suscripciones (administradores):** `/subscribe <type|all> [min_priority]`, `/unsubscribe <type|all>`, `/filters`, `/pause`, `/resume`

---

## Estructura del repositorio

```text
bot-telegram/
├── AGENTS.md        # Reglas y arquitectura del servicio
├── README.md        # Documentación general
├── .gitignore       # Exclusiones Python, secretos y datos locales
├── images/          # Logotipo oficial e iconos (SVG y PNG)
└── src/             # Código fuente Python del bot
```

---

## Autoría y contacto

Creado por **Raúl Caro Pastorino (`@raupulus`)**, desarrollador Full Stack senior (PHP/Laravel, Python, PostgreSQL, JavaScript/Vue, Tailwind CSS), administrador de sistemas Linux/VPS y entusiasta del software libre, hardware *maker* e IoT.

- **Web / Portfolio:** [https://raupulus.dev](https://raupulus.dev)
- **GitHub:** [https://github.com/raupulus](https://github.com/raupulus)
- **GitLab:** [https://gitlab.com/raupulus](https://gitlab.com/raupulus)
- **Correo público:** `public@raupulus.dev`
