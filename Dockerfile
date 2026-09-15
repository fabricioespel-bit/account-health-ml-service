FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Instala dependências do ambiente virtual
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src/ src/
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app /app/
ENV PATH="/app/.venv/bin:$PATH"

ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "account_health.service.main:app", "--host", "0.0.0.0", "--port", "8000"]


