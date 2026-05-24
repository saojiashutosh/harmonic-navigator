FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ffmpeg: required so librosa/audioread can decode JioSaavn's AAC/.mp4
# audio streams (libsndfile alone cannot read AAC).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libsndfile1 ffmpeg dos2unix ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Serve over ASGI (Daphne) so HTTP and WebSocket traffic share one process.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "core.asgi:application"]
