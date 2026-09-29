# VoiceEval backend — uv-based image.
# Shared by the api and worker services; the runner reuses it with a different
# command for a disposable execution container.

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Install the project itself.
COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "voiceeval.main:app", "--host", "0.0.0.0", "--port", "8000"]
