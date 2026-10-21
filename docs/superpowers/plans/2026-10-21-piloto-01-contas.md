# Contas, aprovação e administração — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or, if chosen by the user, superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aprovar participantes e permitir cliente/oficina na mesma identidade, com administradores equivalentes e ações rastreáveis.

**Architecture:** Separar participação de autenticação e representação de oficina. Acrescentar auditoria transacional e usar dependências explícitas nas rotas protegidas. Adaptar o frontend à identidade retornada pelo servidor.

**Tech Stack:** Stack existente; pytest, Vitest e PostgreSQL para migração/concorrência.

**Spec:** [Seções 3, 11–14; A01–A03 e A20](../specs/2026-10-21-piloto-nota-tecnica-design.md).

## Global Constraints

Aplicam-se os contratos, convenções B:/F:, verificações e limites do [plano de coordenação](2026-10-21-piloto-00-coordenacao.md). Este plano não aprova oficinas nem veículos automaticamente. Cadastro público nunca concede `is_admin`.

## Review Focus

- Contas antigas: comuns migram pendentes e administradores antigos permanecem administradores aprovados; T1.
- Cadastro malicioso com privilégios no JSON: recusar atributos de autoridade; T1.
- Duas decisões para a mesma versão: somente uma vence e a outra recebe 409; T2.
- Remoção concorrente dos últimos administradores e autoaprovação: impedir; T2.
- Token presente mas expirado, perfil pendente ou resposta não JSON: interface resolve o estado sem liberar telas nem ficar carregando; T3.

### Task 1 — T1: Identidade e auditoria sem privilégios implícitos

**Arquivos:** alterar `B:app/modules/users/{models,schemas,service}.py`, `B:app/db/base.py`, `B:tests/test_auth_users.py`; criar `B:app/modules/audit/{__init__,models,service}.py`, `B:alembic/versions/20261021_0005_participation_audit.py`, `B:tests/test_participation_models.py` e `B:tests/integration/test_identity_migration.py`.

**Interfaces:** produzir `ParticipationStatus(pending, approved, rejected, suspended)`, campos `User.is_admin`, `participation_status`, `participation_version`, `participation_reason`; `UserRead.capabilities: list[str]` com `customer` para aprovados, `workshop_owner` apenas com representação aprovada e `admin` quando aplicável. Produzir `AuditEvent` e `append_audit` conforme P00; não guardar segredo ou arquivo no evento.

- [ ] Adicionar `test_public_registration_cannot_set_privileges`: `assert response.status_code == 422` para `is_admin=true` ou `participation_status=approved`; `test_customer_registration_starts_pending`: `assert body['participation_status'] == 'pending'` e `assert body['is_admin'] is False`. Preservar teste existente que recusa `profile_type=admin`, com 400.
- [ ] Executar `uv run pytest tests/test_participation_models.py tests/test_auth_users.py -q`; deve falhar nos novos comportamentos, sem falhas de importação por ambiente.
- [ ] Implementar migração aditiva: ler o enum legado efetivamente persistido; migrar antigos `ADMIN` como aprovados, demais como pendentes. Aceitar `profile_type` legado comum como intenção de onboarding, nunca como representação aprovada. Manter resposta legada enquanto consumidores migram; autorização nova usa os novos campos. Registrar modelos na metadata. Testar migração com dados nos dois formatos de enum encontrados, sem promover contas comuns.
- [ ] Executar os testes acima e `uv run pytest tests/integration/test_identity_migration.py -q` com `TEST_POSTGRES_URL` já configurada para banco descartável; exigir zero falhas e dados preservados. O valor da variável é obtido do ambiente de testes, não copiado do banco operacional.
- [ ] Commit sugerido: `feat: separate pilot participation from account identity`.

### Task 2 — T2: Aprovações, privilégios e conflitos de decisão

**Arquivos:** alterar `B:app/modules/auth/dependencies.py`, `B:app/modules/admin/{router,service}.py` e rotas operacionais em `B:app/modules/{garage,vehicles,maintenance,documents,workshops}/router.py`; criar `B:app/modules/admin/{schemas,participation}.py`, `B:app/cli/{__init__,bootstrap_admin}.py`, `B:tests/test_participation_admin.py`, `B:tests/integration/test_admin_concurrency.py`; ajustar helpers em `B:tests/{conftest,test_maintenance,test_admin_validation}.py`.

**Interfaces:** produzir `get_approved_participant` no arquivo de dependências; `review_participant(session, *, actor, user_id, decision, expected_version, reason) -> User`; `set_admin_access(session, *, actor, user_id, enabled, reason) -> User`. Endpoints: `GET /admin/participants?status=pending`, `PATCH /admin/participants/{id}/review`, `PATCH /admin/users/{id}/admin-access`; decisões recebem `expected_version`. Manter `get_current_user` para sessão/perfil pendente.

- [ ] Adicionar testes de conta pendente com JWT nas rotas operacionais: `assert response.status_code == 403`; aprovar com administrador libera a mesma rota. Para versão antiga, `assert response.status_code == 409`; para autoaprovação e revogação do último administrador, `assert response.status_code == 409`. Conferir evento de auditoria e rollback conjunto em falha.
- [ ] Executar `uv run pytest tests/test_participation_admin.py -q`, confirmando falha pelos comportamentos ausentes.
- [ ] Implementar decisões transacionais com comparação de versão e bloqueio das alterações de privilégio. Serializar mudanças do conjunto de administradores no PostgreSQL para proteger o último ativo. CLI `python -m app.cli.bootstrap_admin --email` recebe o e-mail da identidade existente como argumento obrigatório em execução operacional restrita, sem senha via argumento nem endpoint de bootstrap. Atualizar helpers antigos para aprovação explícita via fixture de banco; não criar bypass de aprovação no código de produto.
- [ ] Executar testes direcionados, suite existente de autenticação e testes PostgreSQL com duas sessões concorrentes; testar que duas revogações não deixam zero administradores.
- [ ] Commit sugerido: `feat: add audited pilot participation reviews`.

### Task 3 — T3: Sessão, experiência de aprovação e navegação

**Arquivos:** alterar `B:app/core/config.py`, `B:app/main.py`, `B:.env.example`; criar `B:tests/test_cors.py`; alterar `F:src/lib/api/{client,auth,types}.ts`, `F:src/components/layout/{AuthGuard,AppShell,AdminShell}.tsx`, `F:src/app/router.tsx`, `F:src/features/auth/pages/{LoginPage,RegisterPage}.tsx`; criar `F:src/lib/auth/SessionProvider.tsx`, `F:src/features/auth/pages/PilotStatusPage.tsx`, `F:src/features/admin/pages/ParticipantQueuePage.tsx`, `F:src/lib/api/participants.ts`, `F:src/components/layout/AuthGuard.test.tsx`, `F:src/features/admin/pages/ParticipantQueuePage.test.tsx`.

**Interfaces:** `SessionProvider` expõe `{user, status, refresh, logout}`, onde `status` é `loading | anonymous | authenticated`; `AuthGuard` recebe `requireApproved?: boolean`, `requireAdmin?: boolean`. `/app/participacao` permite perfil autenticado pendente; `/admin/participantes` exige admin. API expõe os novos campos de P01-T1; frontend não deriva privilégio do JWT local.

- [ ] Testar: sessão com token inválido termina em login; pendente termina em `/app/participacao`; aprovado com capacidades cliente/oficina mantém ambas as navegações; não admin não renderiza fila. `assert` de CORS via teste: preflight da origem configurada retorna cabeçalho permitido e outra origem não. Testar erro textual/502 e 204 no cliente HTTP.
- [ ] Executar `uv run pytest tests/test_cors.py -q`; em `F:`, `npm run test -- --run src/components/layout/AuthGuard.test.tsx src/lib/api/client.test.ts`; confirmar falhas de comportamento.
- [ ] Implementar consulta a `/users/me`, logout com limpeza, redirecionamento por estado, fila com motivo e versão. Trocar link quebrado de oficinas para `/app/oficinas`; adicionar rotas de entrada para `/app` e `/admin` e página de rota desconhecida. Configurar origens de CORS explicitamente por ambiente, sem curinga. Mostrar erros de aprovação; nunca transformá-los em lista vazia.
- [ ] Executar verificações completas dos dois repositórios de P00. Conferir cadastro → pendente → aprovação por outro admin → acesso e navegação de oficina sem segunda conta.
- [ ] Commit sugerido em cada repo: `feat: connect pilot participation and session flows`.

**Saída:** A01–A03 exercitados e telas de aprovação utilizáveis. Registrar commits e resultados em P00 antes de iniciar P02.
