FROM python:3.12-slim

# OpenBasin server. No telemetry, no phone-home — the only outbound traffic at
# runtime is to your configured LLM and action targets.

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code.
COPY server/ ./server/

# Persistent SQLite store lives here; mount a volume over it in compose.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080

# config.yaml and pipelines/ are mounted at runtime (see docker-compose.yml).
CMD ["python", "-m", "server"]
