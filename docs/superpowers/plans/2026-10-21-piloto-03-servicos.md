# Oficinas, serviços e moderação — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or, if chosen by the user, superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Publicar uma única manutenção comprovada e reconhecida, com origem cliente ou oficina e contestação auditável.

**Architecture:** Separar representação da oficina, versão do atendimento, decisão documental e reconhecimento do cliente. A política de publicação é a única origem de elegibilidade para consulta e ranking. Convites não concedem vínculo nem aprovação.

**Tech Stack:** Stack existente; PostgreSQL para versões, unicidade e concorrência; R2 privado de P02.

**Spec:** [Seções 3.3, 5, 6, 10–13; A07–A12 e A20](../specs/2026-10-21-piloto-nota-tecnica-design.md).

## Global Constraints

Aplicam-se P00–P02. Todo serviço exige comprovante e análise de sua versão atual. Representação aprovada só autoriza atendimentos daquela oficina. Nunca permitir escolher livremente `author_user_id`, confirmação ou aprovação no payload público.

## Review Focus

- CNPJ existente, conta com duas capacidades e reivindicação por pessoa errada: T1.
- Registro antigo `completed`, versão alterada e comprovante substituído não herdam publicação: T2.
- Convite vencido, usado, reemitido ou aberto por outra conta não confirma o atendimento: T3.
- Sugestão de duplicidade não revela dados privados nem mescla dois serviços reais no mesmo dia: T3.
- Contestação após confirmação e decisão concorrente não mantêm ranking/publicação ativos: T4.

### Task 1 — T1: Oficina, comprovação de representação e cadastro utilizável

**Arquivos:** alterar `B:app/modules/workshops/{models,schemas,service,router}.py`, `B:app/modules/documents/{models,schemas,service}.py`, `B:app/modules/admin/router.py`; criar `B:app/modules/workshops/claims.py`, `B:alembic/versions/20261021_0007_workshop_claims.py`, `B:tests/test_workshop_claims.py`; alterar `F:src/lib/api/workshops.ts`, `F:src/features/workshops/{components/WorkshopForm.tsx,pages/NewWorkshopPage.tsx,pages/WorkshopProfilePage.tsx}`, `F:src/app/router.tsx`; criar `F:src/features/admin/pages/WorkshopClaimsPage.tsx`, `F:src/features/workshops/pages/WorkshopClaimPage.tsx` e `WorkshopClaimPage.test.tsx`.

**Interfaces:** `WorkshopClaim` identifica solicitante, oficina, documentos, versão, decisão e motivo. `POST /workshops/{id}/claims`, `GET /workshops/claims/me`, `GET /admin/workshop-claims`, `PATCH /admin/workshop-claims/{id}/review`; revisão recebe `expected_version`. `POST /workshop-claims/{id}/documents/upload-intents` reutiliza inspeção e leitura de P02. Produzir `require_workshop_responsibility(session, user_id: int, workshop_id: int) -> WorkshopUser`.

- [x] Testar que CNPJ cadastrado abre reivindicação sem segunda oficina; oficina de referência criada por cliente não aparece como gerenciada; aprovação da pessoa não aprova representação. Conta cliente aprovada reivindica e mantém garagem após aprovação. Outro solicitante não lê comprovante; admin não aprova sua própria oficina. `assert workshop_count == 1` e `assert managed_before == []`.
- [x] Executar `uv run pytest tests/test_workshop_claims.py tests/test_workshops.py -q`; confirmar falhas esperadas.
- [x] Acrescentar alvo de documento para `workshop_claim_id`, tornando veículo opcional somente nesse propósito com constraint de alvo válido. Oficina `owner_claimed` não cria responsável verificado automaticamente. Cadastro frontend envia endereço e `source` explícitos; fonte não concede autoridade. Perfil público usa a implementação conectada em `features/workshops`, com contato comercial público; dados de representação ficam privados.
- [x] Executar testes backend e `npm run test -- --run src/features/workshops/pages/WorkshopClaimPage.test.tsx` em F:. Conferir aprovação separada e perfil público real.
- [x] Commit sugerido: `feat: add moderated workshop ownership claims` em cada repositório alterado.

### Task 2 — T2: Revisões e política única de publicação

**Arquivos:** alterar `B:app/modules/maintenance/{models,schemas,service,router}.py`, `B:app/modules/documents/{models,service}.py`, `B:app/modules/public/service.py`, `B:app/modules/ranking/service.py`; criar `B:app/modules/maintenance/{publication,revisions,moderation}.py`, `B:alembic/versions/20261021_0008_maintenance_revisions.py`, `B:tests/{test_publication_policy,test_maintenance_moderation}.py`, `B:tests/integration/test_maintenance_migration.py`; alterar `B:app/modules/admin/router.py`.

**Interfaces:** `MaintenanceRecord` mantém identidade/origem/autoria e `current_revision_id`; `MaintenanceRevision` guarda dados e estados aprovados na spec. Produzir `PublicationFacts(submitted, evidence_approved, admin_approved, customer_acknowledged, link_active, dispute_open)` e `is_publication_eligible(facts) -> bool`; `published_maintenance_select() -> Select[tuple[MaintenanceRecord]]` inclui apenas revisão atual elegível. `POST /maintenance-records/{id}/submit`, `GET /admin/maintenance-reviews`, `GET /admin/maintenance-reviews/{id}`, `PATCH /admin/maintenance-reviews/{id}` com `expected_version`, decisão, motivo e `public_description` revisada.

- [x] Adicionar matriz de `test_publication_policy`: a conjunção dos cinco requisitos positivos com disputa falsa retorna `True`; trocar qualquer positivo por falso retorna `False`; `dispute_open=True` retorna `False`. Testar origem cliente com `author_acknowledged` e origem oficina com confirmação pendente. Custo negativo, descrição vazia e datas incoerentes retornam 422. Serviço sem comprovante verificado não pode ser enviado.
- [x] Executar `uv run pytest tests/test_publication_policy.py tests/test_maintenance_moderation.py -q`; confirmar falhas pelos comportamentos ausentes.
- [x] Migrar manutenção legada para revisão pendente, sem publicação automática por `completed`. Documentos são associados explicitamente à revisão; troca não herda aceite. Criar manutenção de oficina usando a responsabilidade de T1, sem exigir vínculo pessoal do funcionário com a placa. Para cliente, exigir P02 na submissão. Listagem própria combina serviços publicados com os privados em que o ator é autor ou destinatário autorizado; vínculo ativo não revela rascunhos privados de outros remetentes. Submissão não significa conclusão administrativa; usar comparação de versão nas decisões. Atualizar prévia/ranking existentes para a seleção canônica imediatamente, mesmo antes de P04, evitando vazamento durante a transição.
- [x] Executar testes de domínio e migração PostgreSQL; confirmar que registro legado, comprovante pendente, cliente sem vínculo ativo e revisão ultrapassada não publicam. Decisão e auditoria devem fazer rollback juntas.
- [x] Commit sugerido: `feat: version and moderate maintenance publication`.

### Task 3 — T3: Convite, reconhecimento e associação de duplicidade

**Arquivos:** criar `B:app/modules/maintenance/{invitations,acknowledgements,duplicates}.py`, `B:alembic/versions/20261021_0009_service_invitations.py`, `B:tests/{test_service_invitations,test_service_duplicates}.py`; alterar `B:app/modules/maintenance/{models,schemas,router}.py` e `B:app/modules/vehicles/access.py`.

**Interfaces:** `POST /maintenance-records/{id}/invitations` cria/reemite convite e devolve metadados, não token em listagens; `POST /service-invitations/accept` recebe token no corpo; `POST /maintenance-records/{id}/acknowledge` recebe `revision_id`. `POST /maintenance-records/{id}/associate` recebe outro registro e versões; resolução definitiva é administrativa. `ServiceInvitation` armazena hash do token, nonce aleatório sem dados pessoais, validade de sete dias e consumo. Token opaco autentica o nonce por HMAC com chave exclusiva de convites, mantida fora do banco; o worker pode reconstruí-lo para envio sem persistir a credencial em claro. Link emitido usa fragmento do frontend; segredo nunca vai para logs ou auditoria.

- [ ] Testar `expires_at == created_at + timedelta(days=7)`; token vencido/reemitido/consumido não associa. Cliente pendente ou sem vínculo ativo não confirma e não consome o token prematuramente. Possuir link sozinho não revela serviço privado. Duas confirmações simultâneas produzem um reconhecimento da revisão. Duas origens do mesmo atendimento resultam em uma identidade publicada e uma contagem; mesma data/placa sozinhas não mesclam.
- [ ] Executar `uv run pytest tests/test_service_invitations.py tests/test_service_duplicates.py -q`; confirmar falha do comportamento ausente.
- [ ] Guardar intenção de resgate autenticada, não reconhecimento, quando faltar aprovação/vínculo. Exigir remetente autorizado para convite. Associação mantém autores e comprovantes com acesso por remetente; administrador resolve quando correspondência envolve informação privada. Marcar registro secundário com `superseded_by_id`, impedindo contagem dupla; revisão consolidada volta às aprovações aplicáveis. Não criar vaga comercial por aceitar convite. Preparar evento auditado para notificação de P06; não enviar mensagem externa nesta etapa.
- [ ] Executar testes de convite, duplicidade e publicação, incluindo tentativa com outra conta e sugestão sem revelar comprovantes. Token só é consumido na associação válida.
- [ ] Commit sugerido: `feat: reconcile workshop services with customer acknowledgements`.

### Task 4 — T4: Correções e contestação sem sobrescrita do cliente

**Arquivos:** criar `B:app/modules/maintenance/disputes.py`, `B:alembic/versions/20261021_0010_service_disputes.py`, `B:tests/test_service_disputes.py`; alterar `B:app/modules/maintenance/{models,schemas,revisions,router,publication}.py`, `B:app/modules/admin/router.py`.

**Interfaces:** `POST /maintenance-records/{id}/disputes` com motivo e versão; `GET /admin/service-disputes`; `PATCH /admin/service-disputes/{id}` com resolução `request_changes | reject | resolved`, motivo e versão; `PATCH /maintenance-records/{id}` cria nova revisão em mudança relevante. Documento de contestação usa propósito restrito ao seu remetente/admin. Manter decisões separadas do reconhecimento.

- [ ] Testar serviço publicado → contestado: `assert eligible is False` e avaliação deixa de contribuir. Admin não pode converter recusa em `confirmed`. Edição de custo, oficina, data ou documento cria outra revisão com análise pendente e reconhecimento reiniciado; a versão antiga continua consultável pelos atores autorizados. Contestação após confirmação é permitida; reabertura sem nova justificativa é rejeitada.
- [ ] Executar `uv run pytest tests/test_service_disputes.py -q`; confirmar falhas esperadas.
- [ ] Implementar decisões com controle de versão e transação. Clientes podem contestar sem assinatura vigente; oficina só responde, não apaga disputa. Retirar publicação assim que houver disputa/mudança relevante e restaurar somente quando todos os requisitos da revisão atual estiverem satisfeitos. Encerramento registra justificativa; remoção física de histórico/decisões não é endpoint do piloto.
- [ ] Executar testes de disputa e publicação com decisões concorrentes no PostgreSQL, sem duplicar eventos nem manter contribuição pública de versão inelegível.
- [ ] Commit sugerido: `feat: preserve maintenance disputes and revision history`.

### Task 5 — T5: Jornadas de cliente, oficina e administração conectadas

**Arquivos:** alterar `F:src/lib/api/{maintenance,admin,documents}.ts`, `F:src/features/maintenance/{components/MaintenanceForm.tsx,components/MaintenanceTimeline.tsx,pages/NewMaintenancePage.tsx}`, `F:src/features/garage/pages/GarageVehicleDetailPage.tsx`, `F:src/app/router.tsx`; criar `F:src/features/maintenance/pages/{MaintenanceDetailPage,ServiceInvitationPage,PendingServicesPage}.tsx`, `F:src/features/workshops/pages/WorkshopServicesPage.tsx`, `F:src/features/admin/pages/{MaintenanceReviewPage,ServiceDisputesPage}.tsx` e testes junto a cada página nova.

**Interfaces:** corrigir cliente HTTP para `/vehicles/{id}/maintenance-records`, `service_date`, IDs numéricos e custos decimais serializados como strings. Oficina usa `POST /workshops/{id}/maintenance-records` e `GET /workshops/{id}/maintenance-records`; criar essas rotas no backend durante T2 se ainda não expostas. Detalhe separa visão privada do serviço e a futura projeção comprada.

- [ ] Testar: formulário válido envia categoria, sistema, data e valores separados; timeline carrega a resposta real. Oficina vê somente seus atendimentos e pendências; cliente confirma versão correta ou contesta com motivo. Convite aguarda conta/vínculo em vez de mostrar sucesso falso. Admin abre comprovante e decide; 409 pede atualizar a versão.
- [ ] Executar em F: `npm run test -- --run src/features/maintenance src/features/workshops src/features/admin`; confirmar os comportamentos novos falhando antes da conexão.
- [ ] Conectar upload e submissão do cliente, painel da oficina, convite, reconhecimento, correção e filas administrativas. Usar permissões do servidor; distinguir rascunho, análise pendente, confirmação pendente, contestado e publicado. Em retomada de convite, limpar o fragmento da URL depois de capturá-lo, sem persistir token em analytics ou logs.
- [ ] Executar verificações completas de P00 e acompanhar ambas as origens, incluindo cliente sem conta, duplicidade e contestação após confirmação.
- [ ] Commit sugerido em cada repo alterado: `feat: connect workshop and customer service journeys`.

**Saída:** serviços comprovados e moderados publicam somente na versão reconhecida; P04 pode consumir a seleção canônica sem reinventar a regra.
