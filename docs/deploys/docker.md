# Despliegue con Docker (`docker.md`)

Guía verificada directamente contra [`Dockerfile`](../../Dockerfile), [`docker-compose.yml`](../../docker-compose.yml), [`.dockerignore`](../../.dockerignore) y [`.env.example`](../../.env.example).

---

## 1. Resumen del contenedor

- **Imagen base:** `python:3.12-slim`
- **Instalación:** `pip install --no-cache-dir .` (resuelve dependencias desde [`pyproject.toml`](../../pyproject.toml)).
- **Usuario de ejecución:** usuario sin privilegios `botuser` (UID no-root creado en el `Dockerfile`).
- **Directorio de trabajo:** `/app` (`src/` y `images/` copiados).
- **Persistencia:** volumen `/app/data` con variable de entorno `BOT_DB_PATH=/app/data/bot.db` definida en el `Dockerfile`.
- **Comando de arranque:** `CMD ["python", "-m", "src.main"]`.

---

## 2. Requisitos previos en el host / VPS

1. Docker Engine + Docker Compose v2 (`docker compose`).
2. Acceso de red desde el contenedor hacia el servicio `web/`:
   - `WEB_API_BASE_URL` (HTTP/HTTPS hacia `/api/v1/*`)
   - `REVERB_WS_URL` (`ws://` o `wss://` hacia Laravel Reverb)
3. Un token válido de `@BotFather` (`TELEGRAM_BOT_TOKEN`).

---

## 3. Pasos de despliegue

1. Preparar variables de entorno en `bot-telegram/` sin versionar `.env`:
   ```bash
   cp .env.example .env
   ```
2. Rellenar en `.env` al menos:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_ADMIN_IDS` (IDs numéricos separados por coma)
   - `WEB_API_BASE_URL` y `REVERB_WS_URL` apuntando al servicio `web/` accesible desde el contenedor *(nota: dentro de Docker, `127.0.0.1` apunta al propio contenedor del bot, no al host; usar URL pública `https://...` / `wss://...` o `host.docker.internal` / red compartida según topología del VPS)*
   - `REVERB_APP_KEY` y `REVERB_CHANNEL` coincidentes con `web/`
3. Construir y levantar en segundo plano:
   ```bash
   docker compose up -d --build
   ```
4. Verificar logs de arranque:
   ```bash
   docker compose logs -f bot-telegram
   ```
   Deben aparecer en inglés líneas `INFO` confirmando inicialización y suscripción al canal WebSocket de Reverb (`Subscribed to public WebSocket channel '...'`).

---

## 4. Persistencia SQLite y permisos de `./data`

- [`docker-compose.yml`](../../docker-compose.yml) monta `./data:/app/data` con política `restart: unless-stopped`.
- Como la imagen fija `ENV BOT_DB_PATH=/app/data/bot.db` y corre como `botuser`, si creas `./data` previamente como `root` en un VPS Linux, asegúrate de que el proceso `botuser` del contenedor tenga permiso de escritura sobre `./data` (donde SQLite WAL creará `bot.db`, `bot.db-wal` y `bot.db-shm`).
- **Copia de seguridad recomendada:** al usar modo WAL, realiza backup en frío parando el contenedor o usando `.backup` de `sqlite3` sobre `./data/bot.db` en lugar de copiar solo el fichero principal en caliente sin `-wal`/`-shm`.

---

## 5. Actualización y comprobación mínima

```bash
git pull
docker compose up -d --build
docker compose logs --tail=50 bot-telegram
```

---

> Creado: 2026-11-20 · Última revisión: 2026-11-20
