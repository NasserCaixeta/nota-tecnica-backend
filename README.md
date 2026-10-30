# Nota Técnica Backend

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python\&logoColor=fff)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi\&logoColor=fff)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-database-4169E1?logo=postgresql\&logoColor=fff)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker\&logoColor=fff)
![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)

Backend de um web app automotivo para emissão, consulta e gestão de **notas técnicas**, veículos, oficinas, manutenções, documentos, usuários, ranking e módulos administrativos.

## Visão geral

A API foi desenvolvida com FastAPI e arquitetura modular. O objetivo é fornecer uma base segura e organizada para conectar pessoas, veículos, oficinas e documentos técnicos em um sistema automotivo com consultas públicas, autenticação, administração e fluxos de pagamento.

## Funcionalidades

* Autenticação e usuários.
* Gestão de veículos.
* Gestão de oficinas.
* Registro de manutenções.
* Documentos e notas técnicas.
* Consulta pública de informações.
* Módulo administrativo.
* Ranking e métricas.
* Módulo de pagamentos.
* Rotas versionadas em `/api/v1`.
* Migrações com Alembic.
* Testes automatizados.

## Tecnologias

* **Python 3.12+**
* **FastAPI**
* **Uvicorn**
* **SQLAlchemy**
* **PostgreSQL**
* **Alembic**
* **Pydantic / Pydantic Settings**
* **Docker / Docker Compose**
* **Pytest**
* **Ruff**

## Estrutura do projeto

```txt
app/
├── api/           # Rotas principais e versionamento da API
├── core/          # Configurações, segurança e exceções
├── db/            # Banco de dados e sessão
├── integrations/  # Integrações externas
├── modules/       # Módulos de domínio da aplicação
└── main.py        # Inicialização da API
```

### Módulos de domínio

```txt
modules/
├── admin/
├── auth/
├── documents/
├── maintenance/
├── payments/
├── public/
├── ranking/
├── users/
├── vehicles/
└── workshops/
```

## Como executar localmente

### Pré-requisitos

* Python 3.12+
* PostgreSQL
* Docker e Docker Compose, caso prefira rodar via containers
* `uv` instalado, caso use execução local

### Opção 1: Docker Compose

```bash
git clone https://github.com/NasserCaixeta/nota-tecnica-backend.git
cd nota-tecnica-backend
cp .env.example .env
docker compose up -d postgres redis
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Opção 2: Execução local

```bash
git clone https://github.com/NasserCaixeta/nota-tecnica-backend.git
cd nota-tecnica-backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

A documentação da API ficará disponível em:

```txt
http://localhost:8000/docs
```

## Variáveis de ambiente

Use `.env.example` como referência. Em geral, configure:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/nota_tecnica
JWT_SECRET_KEY=<segredo-aleatorio>
BACKEND_CORS_ORIGINS=["http://localhost:5173"]
```

> Não versionar credenciais reais ou chaves sensíveis.

## Migrações

```bash
uv run alembic revision --autogenerate -m "descricao_da_migracao"
uv run alembic upgrade head
```

## Testes

```bash
uv run pytest
```

## Piloto

O [aceite local](docs/superpowers/validation/2026-10-21-piloto-aceite.md) registra critérios A01–A20, comandos e SHAs dos dois projetos. O [roteiro operacional](docs/superpowers/validation/2026-10-21-piloto-operacao.md) cobre Docker, configuração privada, bootstrap, HTTPS, R2, worker/beat e backup/restauração.

`docker-compose.pilot.yml` prepara uma stack privada e exige `.env.pilot` própria; não é o compose de desenvolvimento. Pagamentos usam Stripe Checkout exclusivamente em testes, desativados por padrão. Build local não publica imagens nem disponibiliza o piloto. O Asaas foi substituído; não é necessário concluir seu cadastro. A homologação Stripe e o deploy exigem configuração própria.

Configure `STRIPE_SECRET_KEY` e `STRIPE_WEBHOOK_SECRET` em arquivo privado. O segredo do webhook vem do Stripe, não é uma senha escolhida. Para desenvolvimento local, `stripe listen --forward-to localhost:8000/api/v1/payments/webhooks/stripe` encaminha eventos sem túnel público. Veja o [roteiro Stripe](docs/superpowers/validation/2026-10-30-stripe.md).

```sh
uv run python -m app.cli.pilot_report --from 2026-10-01 --to 2026-10-31
```

O relatório contém agregados sem identidades. Readiness: `/api/v1/ready` (Postgres/Redis); liveness: `/health`. CI local e jornadas Playwright estão documentadas no aceite.

## Autor

Desenvolvido por [Nasser Caixeta](https://github.com/NasserCaixeta).
