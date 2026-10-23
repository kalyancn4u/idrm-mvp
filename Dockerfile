# =============================================================================
#  IDRM MVP — application image
#  One image. Two entrypoints. Used for both the API and the dashboard.
#
#  Build:
#      docker build -t idrm:0.1.0 .
#
#  Run the API:
#      docker run -p 8000:8000 --env-file .env idrm:0.1.0
#
#  Run the dashboard:
#      docker run -p 5000:5000 --env-file .env idrm:0.1.0 \
#          gunicorn -w 4 -b 0.0.0.0:5000 "dashboard:create_dashboard()"
# =============================================================================

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# ---- system dependencies -----------------------------------------------------
# libpq5 for psycopg2; libgeos + libproj + libgdal for GeoAlchemy2/PostGIS
# client; curl for the healthcheck.  build-essential is installed only in the
# builder layer and purged before the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libgeos-c1v5 \
        libproj25 \
        libgdal32 \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---- python dependencies -----------------------------------------------------
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libgeos-dev \
        libproj-dev \
        libgdal-dev \
    && pip install -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

# ---- application -------------------------------------------------------------
COPY . .

# ---- non-root user -----------------------------------------------------------
RUN useradd --create-home --uid 10001 --shell /bin/bash idrm \
    && chown -R idrm:idrm /app
USER idrm

# ---- runtime -----------------------------------------------------------------
EXPOSE 8000 5000

# Default entrypoint runs the FastAPI app.  Override the command to run the
# Flask dashboard instead.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

CMD ["gunicorn", \
     "-w", "4", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "-b", "0.0.0.0:8000", \
     "app.main:app"]
