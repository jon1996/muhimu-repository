FROM python:3.12-slim AS base

ARG APP_ROLE=erp
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ROLE=${APP_ROLE}

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN sed -i 's/\r$//' scripts/entrypoint_web.sh scripts/entrypoint_migrate.sh \
    && chmod +x scripts/entrypoint_web.sh scripts/entrypoint_migrate.sh \
    && mkdir -p /app/staticfiles /app/media

EXPOSE 8000

# Cible développement (compose actuel) — runserver.
FROM base AS development
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Cible bêta / staging — Gunicorn uniquement.
FROM base AS production
ENV DJANGO_DEBUG=0
CMD ["./scripts/entrypoint_web.sh"]
