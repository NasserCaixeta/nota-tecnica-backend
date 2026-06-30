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

## Initial API Surface

Public:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/workshops`
- `GET /api/v1/workshops/{workshop_id}`
- `GET /api/v1/public/vehicles/{plate}/history-preview`
- `GET /api/v1/public/workshops/ranking`

Authenticated:

- `GET /api/v1/users/me`
- `POST /api/v1/vehicles`
- `GET /api/v1/vehicles`
- `GET /api/v1/vehicles/{vehicle_id}`
- `POST /api/v1/workshops`
- `GET /api/v1/workshops/me`

Maintenance:

- `POST /api/v1/vehicles/{vehicle_id}/maintenance-records`
- `GET /api/v1/vehicles/{vehicle_id}/maintenance-records`
- `GET /api/v1/maintenance-records/{record_id}`
- `PATCH /api/v1/maintenance-records/{record_id}`

Documents:

- `POST /api/v1/vehicles/{vehicle_id}/documents`
- `GET /api/v1/vehicles/{vehicle_id}/documents`
- `GET /api/v1/documents/{document_id}`

Admin:

- `PATCH /api/v1/admin/vehicle-links/{vehicle_link_id}/verification`
- `PATCH /api/v1/admin/documents/{document_id}/review`

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

This repository currently contains the backend MVP foundation. Auth, users, vehicles, workshops, maintenance records, document metadata, manual validation, public history preview, and an initial workshop ranking are implemented. Real file upload/storage, OCR, payments, admin UI, background jobs, and advanced ranking are deferred.
