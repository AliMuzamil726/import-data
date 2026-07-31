# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install --no-install-recommends -y \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN adduser --disabled-password --gecos "" sawie \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R sawie:sawie /app
USER sawie

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/accounts/login/ || exit 1

# Daphne serves both HTTP and WebSockets. Swap in Gunicorn if you drop Channels.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
