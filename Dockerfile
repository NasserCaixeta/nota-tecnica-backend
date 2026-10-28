FROM ghcr.io/astral-sh/uv:0.9.9 AS uv
FROM python:3.13-slim AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --python /usr/local/bin/python

FROM python:3.13-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --uid 10001 --create-home pilot
WORKDIR /app
COPY --from=dependencies /app/.venv /app/.venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*"]
