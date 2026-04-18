FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY scripts/docker-entrypoint.sh /app/scripts/docker-entrypoint.sh

RUN pip install --no-cache-dir .

RUN useradd --create-home ceos \
    && mkdir -p /app/runtime /app/scripts \
    && chmod +x /app/scripts/docker-entrypoint.sh \
    && chown -R ceos:ceos /app
USER ceos

ENV CEOS_STORAGE_ROOT=/app/runtime
EXPOSE 8080

ENTRYPOINT ["scripts/docker-entrypoint.sh"]
