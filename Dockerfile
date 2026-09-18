# ─── build stage ───────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ffmpeg is required for video assembly / muxing / loudnorm
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

# install deps first for better layer caching
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install -e .

# then the source
COPY . .

# non-root user
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["uvicorn", "smauto.api.main:app", "--host", "0.0.0.0", "--port", "8000"]