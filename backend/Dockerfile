FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN groupadd --system app && useradd --system --gid app --create-home app
COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

COPY alembic.ini ./
COPY migrations ./migrations
COPY backend ./backend
RUN mkdir -p /artifacts && chown -R app:app /app /artifacts

USER app
EXPOSE 8000

CMD ["sh", "-c", "uv run alembic upgrade head && exec uv run uvicorn backend.smartrecon_api.main:app --host 0.0.0.0 --port 8000 --workers 1"]

