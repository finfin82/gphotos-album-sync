FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GOOGLE_LANG=de \
    OUTPUT_ROOT=/data/shared \
    HTTP_PORT=8090 \
    POLL_SECONDS=30 \
    CHROME_BINARY=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    WEB_DRIVER_WAIT=25 \
    DOWNLOAD_TIMEOUT=1800 \
    QUEUE_DIR=/queue \
    TEMP_DIR=/tmp/gp-downloads \
    PROFILE_DIR=/profile \
    USE_CHROME_PROFILE=false \
    SKIP_EXISTING=true \
    HEADLESS=true \
    WSL_INSIDE=true

RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        fonts-liberation \
        fonts-dejavu-core \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /data/shared /queue /profile /tmp/gp-downloads

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health')"

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${HTTP_PORT:-8090}"]
