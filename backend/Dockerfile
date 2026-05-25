FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install supercronic for cron-style scheduling without root cron.
# Detect arch at build time so this works on both amd64 and arm64 hosts
# regardless of whether BuildKit passes TARGETARCH.
ARG SUPERCRONIC_VERSION=v0.2.33
RUN arch="$(dpkg --print-architecture)" \
    && curl -fsSL -o /usr/local/bin/supercronic \
         "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-${arch}" \
    && chmod +x /usr/local/bin/supercronic

COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Chromium runtime libs manually + then the browser.
#
# We deliberately avoid `playwright install --with-deps chromium` because
# it tries to apt-install obsolete font packages (`ttf-unifont`,
# `ttf-ubuntu-font-family`) that are no longer available on current
# Debian. Listing the actual runtime libs ourselves gives us a working
# headless Chromium ~400MB lighter than --with-deps would.
#
# Required by the lifeboard.playwright_scraper module — bypasses the
# anti-bot edges on B&H + eBay (both 403 our requests-based scrapers).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
        libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
        libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
        libasound2 libatspi2.0-0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && python -m playwright install chromium

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
