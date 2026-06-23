# Nota Tecnica Backend

Backend API for Nota Tecnica.

## Stack

- FastAPI
- Pydantic Settings
- SQLAlchemy 2.0 async
- PostgreSQL
- Alembic
- Redis
- Celery prepared for future jobs
- Cloudflare R2 prepared for future storage
- uv
- pytest
- ruff

## Local Setup

Prerequisites:

- Python 3.12
- uv
- Docker with Docker Compose

Install dependencies:

```bash
uv sync
```

Copy environment example:

```bash
cp .env.example .env
```

Start local services:

```bash
docker compose up -d
```

If the default ports conflict with local services, override the host ports:

```bash
POSTGRES_HOST_PORT=15432 REDIS_HOST_PORT=16379 docker compose up -d
```

Run migrations:

```bash
uv run alembic upgrade head
```

Start the API:

```bash
uv run fastapi dev app/main.py
```

Healthchecks:

- `GET /health`
- `GET /api/v1/health`

## Verification

Run tests:

```bash
uv run pytest
```

Run lint:

```bash
uv run ruff check .
```

Format:

```bash
uv run ruff format .
```

## Current Scope

This repository currently contains the backend skeleton only. Auth, users, vehicles, maintenance records, document uploads, ranking, payments, admin workflows, and real background jobs are intentionally deferred.
