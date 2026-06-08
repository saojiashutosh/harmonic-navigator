FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Force production settings; core/settings/__init__.py otherwise defaults to dev.
ENV DJANGO_SETTINGS_MODULE=core.settings.production

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libsndfile1 ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# HF Spaces routes traffic to app_port (declared in the Space README, default 7860).
EXPOSE 7860

# Managed DB (Neon) + Redis (Upstash) are persistent and seeded once from a dev
# machine, so production only migrates + collects static, then serves over ASGI
# (Daphne) so HTTP and WebSocket traffic share one process. $PORT overrides 7860.
CMD ["/bin/sh", "-c", "\
    set -e; \
    echo 'Applying database migrations...'; \
    python manage.py migrate --no-input; \
    echo 'Collecting static files...'; \
    python manage.py collectstatic --no-input; \
    PORT=\"${PORT:-7860}\"; \
    echo \"Starting Daphne on 0.0.0.0:${PORT}...\"; \
    exec daphne -b 0.0.0.0 -p \"${PORT}\" core.asgi:application \
"]
