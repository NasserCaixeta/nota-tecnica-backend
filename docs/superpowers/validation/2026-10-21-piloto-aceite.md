# Aceite local do piloto — 28/10/2026

Esta evidência cobre dados sintéticos, PostgreSQL 16, Redis 7, upload HTTP controlado e gateway de teste isolado. Não comprova homologação Asaas remota, entrega SMTP externa ou implantação pública. A CI foi preparada em ambos os repositórios; não foi acionada remotamente.

## Critérios e evidências

Os casos abaixo integram a suíte completa; o catálogo verificável evita duplicar testes de negócio. Cada critério pode exigir outros casos da mesma suíte além do representante listado.

| Critério | Teste representante executado |
|---|---|
| A01 | `tests/test_participation_admin.py::test_pending_account_cannot_operate_with_valid_token` |
| A02 | `tests/test_workshop_claims.py::test_one_account_can_be_customer_and_approved_workshop_responsible` |
| A03 | `tests/integration/test_maintenance_concurrency.py::test_two_service_reviewers_cannot_overwrite_the_same_version` |
| A04 | `tests/test_garage_subscription.py::test_five_total_slots_and_expiry_preserve_reading` |
| A05 | `tests/test_vehicle_access.py::test_declaring_existing_plate_does_not_reveal_previous_history` |
| A06 | `tests/test_vehicle_access.py::test_validated_additional_vehicle_remains_readable_without_subscription` |
| A07 | `tests/test_maintenance_moderation.py::test_legacy_completed_flag_does_not_publish_and_submission_requires_verified_evidence` |
| A08 | `tests/test_maintenance_moderation.py::test_customer_service_publishes_only_current_approved_revision` |
| A09 | `tests/test_service_invitations.py::test_invitation_is_seven_days_and_does_not_bypass_approval_or_vehicle_validation` |
| A10 | `tests/test_service_duplicates.py::test_two_origins_consolidate_into_one_public_identity` |
| A11 | `tests/test_service_disputes.py::test_dispute_after_confirmation_immediately_withdraws_publication` |
| A12 | `tests/test_service_disputes.py::test_relevant_correction_preserves_previous_snapshot_and_requires_new_analysis` |
| A13 | `tests/test_paid_history_access.py::test_bought_history_is_sanitized_and_rechecks_publication` |
| A14 | `tests/test_payment_benefits.py::test_duplicate_confirmations_grant_exact_720_hours_from_verified_time` |
| A15 | `tests/test_paid_history_access.py::test_paid_history_exact_expiry_and_identity_boundaries` |
| A16 | `tests/integration/test_payment_concurrency.py::test_simultaneous_payment_confirmations_create_one_benefit` |
| A17 | `tests/test_garage_subscription.py::test_additional_vehicle_can_acknowledge_and_dispute_without_subscription` |
| A18 | `tests/test_service_reviews.py::test_workshop_responsible_cannot_review_own_workshop` |
| A19 | `tests/test_ranking.py::test_ranking_filters_by_category` |
| A20 | `e2e/{participation,garage,services,history-payments}.spec.ts` — seis jornadas reais |

A20 cobre cadastro/aprovação e bloqueio 403, garagem/documento/revisão, manutenção cliente, oficina/convite/reconhecimento/contestação, histórico pago após evento autenticado duplicado e assinatura/cancelamento. Asserções rejeitam retorno de checkout forjado; APIs de produto usam o mesmo contrato da interface. Recuperação/perfil e notificações têm testes HTTP e de componente; não estão nas seis jornadas de navegador.

## Reprodução

Backend, a partir de B (credenciais abaixo são exclusivamente da infraestrutura local descartável):

```sh
uv sync --frozen
uv run ruff check app tests alembic
uv run ruff format --check app tests alembic
TEST_POSTGRES_URL=postgresql+asyncpg://nota_tecnica:nota_tecnica@localhost:55439/nota_tecnica_pilot_test TEST_REDIS_URL=redis://localhost:55440/15 uv run pytest -q
uv run python -m tests.integration.test_pilot_acceptance
```

Frontend, em F, com os dois diretórios irmãos e banco `nota_tecnica_browser_test` local descartável:

```sh
npm ci
npm run lint
npm run test -- --run
npm run build
npm audit --audit-level=moderate
PLAYWRIGHT_BROWSERS_PATH=/private/tmp/nota-tecnica-playwright npx playwright install chromium
PLAYWRIGHT_BROWSERS_PATH=/private/tmp/nota-tecnica-playwright npm run test:e2e
```

`playwright.config.ts` inicia os dois servidores. A fixture exige `E2E_TEST_RUN=1`, banco local com sufixo `_test` e restaura seu schema; nunca aponte para dados de participantes. O contador de teste usa Redis DB15. O gateway/storage controlados existem apenas em `tests/browser_server.py`; nenhum endpoint de produto libera pagamentos artificialmente.

## Migração e restauração

`tests/integration/test_migration_chain.py` executa upgrade de base vazia e de `20260707_0004` com usuário/documento/manutenção legados, valida enums, preserva privacidade e executa `alembic check`. Ambos passaram com head `20261021_0017`.

```sh
TEST_POSTGRES_URL=postgresql+asyncpg://nota_tecnica:nota_tecnica@localhost:55439/nota_tecnica_pilot_test uv run python -m tests.integration.backup_roundtrip
```

Restauração executada com sucesso em duas bases novas com nomes exclusivos. O script recusa nomes existentes, não usa DROP nem `--clean`, abre dump sem sobrescrever arquivo e preserva usuário/documento/auditoria sintéticos. Objetos R2 não estão no dump e precisam de estratégia independente. A primeira proposta de teste foi recusada pela revisão automática por excluir schema preexistente; essa operação não foi executada. A alternativa segura acima foi validada.

## Resultados e versões

Par de código validado: backend `1943fa17c8966683cd5fed7d50a4da8d53a68b8b`, frontend `2d1b70ae36b36488ef80bc872b10d0722f7d6eb0`.

- Backend: **321 testes passaram**, incluindo PostgreSQL/Redis e cadeia de migrações; Ruff check/format sem diferenças. Aviso de depreciação upstream do TestClient.
- Frontend: instalação `npm ci`, lint, **62 testes**, build e audit concluídos; **zero vulnerabilidades** reportadas.
- Navegador repetido no par commitado: **6/6 passaram em 12,4s**.
- Backup/restauração e migração de base vazia/legada: passaram conforme procedimento acima.

Logs locais sanitizados: `/private/tmp/p06-t3-full.log`, `/private/tmp/p06-ci-ui.log`, `/private/tmp/p06-e2e-committed.log`, `/private/tmp/p06-backup-restore-safe.log`. São evidência temporária da sessão; o índice, comandos e resultados persistem neste documento.

## Pendências externas

- Homologar webhooks, período e cancelamento com Sandbox Asaas real e HTTPS autorizado (P05).
- Executar CI no provedor após publicação autorizada dos commits.
- Autorizar/configurar ambiente público, bucket privado/CORS, HTTPS, SMTP e responsáveis pela operação.
- Avaliar retenção final, suporte, preços e passagem ao MVP comercial antes de cobrança real.

## Preparação operacional P06-T4

Backend327/327 com PostgreSQL/Redis e Ruff; dois Docker builds locais concluídos. Smoke de contêiner validou readiness real, SPA profunda, proxy da API, CLI agregado e ausência de .env/.git/testes na imagem API. Compose e ambos workflows passaram validação local (actionlint). Frontend mantém62/62 da T3; T4 altera apenas embalagem/documentação. Logs locais: `/private/tmp/p06-t4-full.log`, `/private/tmp/p06-docker-api.log`, `/private/tmp/p06-docker-ui.log`, `/private/tmp/p06-container-smoke.log`. [Roteiro e proposta de ambiente/custos](2026-10-21-piloto-operacao.md). Nenhum deploy ou envio de e-mail externo ocorreu.
