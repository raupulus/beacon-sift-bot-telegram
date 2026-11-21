FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BOT_DB_PATH=/app/data/bot.db

WORKDIR /app

# Instalar paquete y dependencias desde pyproject.toml
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY images ./images

RUN pip install --no-cache-dir . \
    && useradd --create-home --shell /usr/sbin/nologin botuser \
    && mkdir -p /app/data \
    && chown -R botuser:botuser /app

USER botuser

VOLUME ["/app/data"]

CMD ["python", "-m", "src.main"]
