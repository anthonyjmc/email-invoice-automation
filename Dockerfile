# Python 3.12 matches CI (.github/workflows/ci.yml). Reproducible runs for Render alternatives, K8s, ACI.
FROM python:3.12-slim-bookworm AS base

WORKDIR /app

# Optional: install ClamAV CLI for UPLOAD_AV_SCAN_COMMAND=clamscan --no-summary {path}
# Build: docker build --build-arg INSTALL_CLAMAV=true -t invoice-app .
# First run still needs virus definitions (e.g. freshclam in an entrypoint or init container).
ARG INSTALL_CLAMAV=false
RUN if [ "$INSTALL_CLAMAV" = "true" ]; then \
    apt-get update \
    && apt-get install -y --no-install-recommends clamav \
    && rm -rf /var/lib/apt/lists/*; \
    fi

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY examples ./examples

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
