FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5

WORKDIR /app

# Runtime libraries required by PostgreSQL clients and WeasyPrint.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        libcairo2 \
        libffi8 \
        libgdk-pixbuf-2.0-0 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libpq5 \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --requirement requirements.txt

COPY . .

RUN mkdir -p /app/data /app/prefect-data \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /app/prefect-data

USER appuser

CMD ["python", "-c", "print('Application image ready. Run a specific command with docker compose run.')"]

FROM runtime AS prefect-runtime

USER root
RUN python -m pip install "prefect>=3.7,<4"
USER appuser

CMD ["python", "-m", "prefect_flows.deployment"]
