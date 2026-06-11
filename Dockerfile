# Dockerfile — imagem unica para app (gunicorn) e worker (rq).
# INFRA-1 (doc 30 Onda 1): usada pelo docker-compose.yml (dev / host alternativo).
# Render usa buildCommand/startCommand proprios (render.yaml), nao este Dockerfile.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencias de build para wheels nativas (psycopg2, etc.). libpq para Postgres.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

# Default: web app. O worker sobrescreve o command no compose/render.
CMD ["gunicorn", "-c", "gunicorn.conf.py", "src.app:app"]
