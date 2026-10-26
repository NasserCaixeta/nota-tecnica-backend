# Piloto Nota Técnica — coordenação da implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution, or superpowers:subagent-driven-development only when the user chooses delegation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o piloto aprovado, em seis entregas verificáveis, preparando o MVP comercial.

**Architecture:** Evoluir os módulos existentes com autorização no servidor, aprovação e direitos comerciais independentes. Compartilhar a política de publicação entre prévia, ranking e histórico comprado. Cada entrega inclui o frontend necessário para usar seu comportamento.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy assíncrono, PostgreSQL, Alembic, R2, React 19, TypeScript e Vite; testes com pytest/Vitest.

**Spec:** [Spec aprovada](../specs/2026-10-21-piloto-nota-tecnica-design.md).

## Global Constraints

- `B:` significa raiz deste backend; `F:` significa raiz de `../nota-tecnica-frontend`. Comandos de frontend são executados em `F:`.
- API em `/api/v1`; prefixo omitido nas tabelas de endpoints destes planos.
- Cadastro aberto, participação aprovada, conta com capacidades combináveis e administradores equivalentes.
- Todo serviço exige comprovante e análise; origem oficina também exige confirmação do cliente.
- Primeiro veículo gratuito; assinatura mensal para cinco no total; compra de uma placa por 720 horas.
- No piloto, somente pagamentos de testes. Sem publicação ou implantação automática na execução dos planos.
- Arquivos até 10 MiB; PDF/JPEG/PNG/WebP; leitura privada assinada por 300 segundos.
- Em cada tarefa funcional: teste que demonstra o comportamento ausente, execução desse teste, implementação, execução passando e commit restrito aos arquivos da tarefa em cada repositório. Nunca usar `git add .`.
- Depois de cada entrega: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`; em `F:`, `npm run test -- --run`, `npm run lint`, `npm run build`. Resultado exigido: saída zero. Resolver regressões concretas; não afirmar sucesso sem executar.
- Testes de PostgreSQL usam banco descartável identificado por `TEST_POSTGRES_URL`; nunca executar limpeza ou migração de testes sobre `DATABASE_URL` de operação.
- Dependências ausentes ou rede indisponível são impedimentos de execução, não falhas aprovadas. Não atualizar lockfiles apenas para contornar o ambiente.
- Os dois repositórios exigem commits e revisão próprios. Durante esta etapa de planejamento, somente documentos e sua inclusão no Git são alterados.

## Review Focus

- Migração não aprova participantes/serviços antigos: P01-T1, P03-T2 e P06-T3.
- Sessão ou rota antiga não contorna aprovação: P01-T2/T3 e P02-T1.
- Identidade, comprovante ou compra não concedem direitos diferentes dos previstos: P02-T2, P03-T3 e P05-T3.
- Evento financeiro repetido e aprovação concorrente não duplicam benefícios/decisões: P01-T2, P03-T2 e P05-T2.
- Cada critério A01–A20 tem tarefas abaixo e uma jornada de integração em P06-T3.

## Entregas e dependências

| Ordem | Plano | Saída utilizável | Depende de |
| --- | --- | --- | --- |
| 1 | [P01 — contas e aprovação](2026-10-21-piloto-01-contas.md) | Cadastro pendente, análise, capacidades e sessão coerente. | Base existente. |
| 2 | [P02 — garagem e documentos](2026-10-21-piloto-02-garagem.md) | Vínculo analisável, privacidade e uma vaga gratuita coerente em toda API. | P01. |
| 3 | [P03 — oficinas e serviços](2026-10-21-piloto-03-servicos.md) | Serviços nas duas origens, reconhecimento, disputas e publicação. | P01 e P02. |
| 4 | [P04 — consulta e ranking](2026-10-21-piloto-04-consulta-ranking.md) | Prévia real e ranking explicável com dados elegíveis. | P03. |
| 5 | [P05 — pagamentos e assinatura](2026-10-21-piloto-05-pagamentos.md) | Acesso por 30 dias e cinco veículos em testes. | P02–P04. |
| 6 | [P06 — operação e verificação](2026-10-21-piloto-06-operacao.md) | Notificações, recuperação, CI, homologação e roteiro operacional. | P01–P05. |

Sequência nativa recomendada. Não há necessidade de agentes paralelos para executar os contratos interdependentes. O plano de pagamentos propõe Asaas Sandbox, isolado por adaptador; sua homologação remota depende de conta e credenciais de testes, não necessárias às entregas 1–4.

## Contratos compartilhados

| Dono | Contrato que as entregas posteriores consomem |
| --- | --- |
| P01 | `get_current_user` autentica; `get_approved_participant` exige participação; `get_current_admin_user` exige administrador ativo/aprovado. `UserRead` inclui `participation_status`, `is_admin`, `capabilities`; nenhum desses privilégios é concedido pelo cadastro público. |
| P01 | `append_audit(session, *, actor_id, action, target_type, target_id, version, reason, metadata) -> AuditEvent`, sem commit interno; gravação na mesma transação da ação. Metadados aceitam JSON sem segredos ou documentos. |
| P02 | `require_active_vehicle_link(session, user_id, vehicle_id) -> VehicleUser`; `get_garage_capacity(session, user_id, now) -> GarageCapacity(limit, free_vehicle_id, writable_vehicle_ids)`. Até P05, capacidade real de uma vaga, sem assinatura fictícia. |
| P02 | `get_document_download(session, document_id, actor, storage) -> DocumentDownloadRead(url, expires_at)`; apenas remetente/admin. `inspect_object` devolve existência, tamanho e tipo real. |
| P03 | `published_maintenance_select() -> Select[tuple[MaintenanceRecord]]`, em `app/modules/maintenance/publication.py`; é a seleção canônica de registros publicáveis. Dados de uma revisão só contribuem depois dos atos necessários sobre aquela revisão. |
| P03 | `is_publication_eligible(facts: PublicationFacts) -> bool`, na mesma unidade, com matriz de aprovação, reconhecimento, evidência e disputa. |
| P05 | `has_history_access(session, user_id, vehicle_id, now) -> bool`; `get_garage_capacity` passa a consultar períodos de assinatura confirmados. |
| P06 | `enqueue_notification(session, *, recipient_id, kind, target_type, target_id, dedupe_key) -> Notification`; persistência transacional e envio posterior. |

Tipos de contrato são definidos nas tarefas donas. Consumidores importam esses tipos; não criam versões paralelas. Novas migrações seguem a cadeia Alembic existente e são sequenciadas conforme os planos.

## Cobertura de aceite

| Critérios da spec | Tarefas principais |
| --- | --- |
| A01–A03 | P01-T1/T2/T3. |
| A04 | P02-T1 e P05-T3. |
| A05–A06 | P02-T1/T2/T3 e P05-T3. |
| A07–A08 | P02-T2 e P03-T2/T5. |
| A09–A10 | P03-T3/T5. |
| A11–A12 | P03-T4/T5. |
| A13 | P04-T1 e P05-T3. |
| A14–A17 | P05-T1/T2/T3/T4. |
| A18–A19 | P04-T2/T3. |
| A20 | Frontend das seis entregas e P06-T3. |

## Acompanhamento

- [x] P01 concluído e verificado: backend 133 testes, frontend 25 testes, lint/format/build aprovados; PostgreSQL inclui migração e concorrência.
- [x] P02 concluído e verificado: backend 158 testes, frontend 28 testes, lint/format/build aprovados; documentos privados e análise por versão.
- [x] P03 concluído e verificado: revisão independente e correções cobertas; suite conjunta com P04-T1: 208 backend/PostgreSQL e 42 frontend, lint/format/build aprovados. Registro: [execução e revisão](../reviews/2026-10-26-piloto-p03.md).
- [ ] P04 concluído e verificado.
- [ ] P05 concluído e verificado, incluindo homologação com provedor de testes.
- [ ] P06 concluído e piloto pronto para decisão de disponibilização.

Não há estimativa em dias: a duração depende da execução inicial das suites e da homologação das integrações. Registrar o resultado e o commit de cada entrega aqui durante a implementação.
