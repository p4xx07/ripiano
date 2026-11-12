FROM python:3.13-slim-trixie
LABEL org.opencontainers.image.source="https://github.com/p4xx07/ripiano"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_NO_DEV=1 UV_FROZEN=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript libzbar0t64 qpdf tesseract-ocr tesseract-ocr-eng tesseract-ocr-ita pngquant unpaper postgresql-client \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.9.26
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen
COPY . .
RUN mkdir -p /data /backup && useradd --system --uid 10001 --home /app ripiano && chown -R ripiano:ripiano /app /data /backup
USER ripiano
EXPOSE 8000
CMD [".venv/bin/gunicorn", "ripiano.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "60"]
