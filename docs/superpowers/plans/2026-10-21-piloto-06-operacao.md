# Operação, notificações e homologação — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or, if chosen by the user, superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Operar o piloto com pendências visíveis, recuperação de acesso e evidências de ponta a ponta.

**Architecture:** Notificações persistidas na mesma transação da ação e envio externo desacoplado. PostgreSQL real valida migrações e concorrência; testes de navegador verificam contratos dos dois repositórios. Implantação é preparada para revisão, sem publicar automaticamente.

**Tech Stack:** Stack existente, Celery/Redis, SMTP de testes, pytest/Vitest e Playwright em dev para jornadas integradas.

**Spec:** [Seções 10–15; A01–A20](../specs/2026-10-21-piloto-nota-tecnica-design.md).

## Global Constraints

Aplicam-se P00–P05. Não afirmar testes executados quando houver dependência ausente. Mensagens externas reais, conta de provedor e implantação exigem autorização operacional; em desenvolvimento usar capturador de e-mail local. Sem dado pessoal, segredo ou URL assinada nos logs de teste.

## Review Focus

- Falha no e-mail não desfaz decisão aprovada nem perde o evento de notificação: T1.
- Token de recuperação expirado/reutilizado e enumeração de e-mail: T2.
- Migração em base com dados, enums legados e rollback de falha intermediária: T3.
- Frontend compilável com testes passando, mas contrato HTTP incompatível: jornadas reais em T3.
- Backup não restaurável e instrução de deploy que liga produção financeira por padrão: T4.

### Task 1 — T1: Pendências no app e entrega confiável de notificações

**Arquivos:** criar `B:app/modules/notifications/{__init__,models,schemas,service,router}.py`, `B:app/integrations/email/{__init__,smtp}.py`, `B:app/integrations/queue/notification_tasks.py`, `B:alembic/versions/20261021_0014_notifications.py`, `B:tests/test_notifications.py`; alterar pontos de decisão em `B:app/modules/admin/participation.py`, `B:app/modules/admin/service.py`, `B:app/modules/workshops/claims.py`, `B:app/modules/maintenance/{moderation,invitations,acknowledgements,disputes}.py`, `B:app/modules/payments/benefits.py`, `B:app/api/v1/router.py`, `B:app/db/base.py`; criar `F:src/lib/api/notifications.ts`, `F:src/features/notifications/pages/NotificationsPage.tsx` e seu teste; alterar shell e roteador.

**Interfaces:** `enqueue_notification(session, *, recipient_id: int, kind: str, target_type: str, target_id: int, dedupe_key: str) -> Notification`, sem commit próprio. `GET /notifications` só destinatário; `POST /notifications/{id}/read`. Tipos: aprovação/rejeição, documentos adicionais, reconhecimento pendente, disputa e benefício comercial. Convite/recuperação têm e-mail; outras ações têm central de pendências. `NotificationDelivery` único por notificação/canal.

- [ ] Testar rollback da ação não deixa notificação; mesma chave não duplica; falha SMTP mantém decisão e entrega pendente; retry tem uma entrega lógica. Usuário B não lê pendência de A. Corpo não inclui CPF, comprovante bruto nem segredo fora do link necessário.
- [ ] Executar `uv run pytest tests/test_notifications.py -q`; confirmar falhas de comportamento.
- [ ] Persistir notificações transacionalmente e despachar por ID após commit; worker recupera pendências mesmo se a fila perder despacho. Convites reconstroem o token autenticado a partir do nonce e da chave externa definidos em P03-T3, sem cópia em claro no banco ou na fila; antes de enviar, conferir se não venceu nem foi substituído/consumido. Configurar capturador SMTP local e templates simples sem marketing. Não enviar mensagens a participantes reais durante desenvolvimento.
- [ ] Executar testes backend e `npm run test -- --run src/features/notifications` em F:. Simular indisponibilidade de Redis/SMTP, recuperar worker e verificar a mesma pendência sem aprovação duplicada.
- [ ] Commit sugerido: `feat: add pilot notifications and reliable delivery`.

### Task 2 — T2: Recuperação, perfil e pedidos de encerramento

**Arquivos:** alterar `B:app/modules/auth/{router,schemas,security}.py`, `B:app/modules/users/{router,schemas,service}.py`; criar `B:app/modules/auth/recovery.py`, `B:alembic/versions/20261021_0015_account_recovery.py`, `B:tests/test_account_recovery.py`; criar `F:src/features/auth/pages/{ForgotPasswordPage,ResetPasswordPage,AccountPage}.tsx` e testes; alterar API de auth e roteador.

**Interfaces:** `POST /auth/forgot-password` responde 202 com mensagem neutra exista ou não a conta; `POST /auth/reset-password` recebe token e nova senha. Token único, hash persistido e validade de 60 minutos. `PATCH /users/me` atualiza campos pessoais permitidos, sem privilégios; alteração de dado usado em validação exige nova análise do vínculo afetado. `POST /users/me/closure-requests` registra pedido para administração, sem apagar histórico auditado.

- [ ] Testar resposta igual para e-mail inexistente; token vencido/reutilizado rejeitado; troca de senha invalida sessões anteriores por `auth_version` ou equivalente verificado no servidor. JSON de perfil com `is_admin` ou participação recebe 422. Pedido de encerramento aparece só para solicitante/admin.
- [ ] Executar `uv run pytest tests/test_account_recovery.py -q`; confirmar falhas esperadas.
- [ ] Implementar recuperação com P06-T1 e segredo fora dos logs; limitar repetição por conta/IP. Criar tela de perfil, recuperação e solicitação administrativa. Não permitir trocar CPF silenciosamente depois de validar vínculos; tratar como pedido administrativo. Migrar `auth_version` com valor inicial sem invalidar sessões anteriores à implantação até que se faça uma ação de segurança.
- [ ] Executar testes de recuperação, sessão e frontend; conferir que conta pendente pode recuperar acesso e continua pendente depois da troca de senha.
- [ ] Commit sugerido: `feat: add safe account recovery and profile requests`.

### Task 3 — T3: Suites, migrações e jornadas com os dois projetos

**Arquivos:** criar `B:tests/integration/{conftest,test_migration_chain,test_pilot_acceptance}.py`, `B:app/core/rate_limit.py`, `B:tests/test_rate_limits.py`, `B:.github/workflows/ci.yml`, `F:playwright.config.ts`, `F:e2e/{participation,garage,services,history-payments}.spec.ts`, `F:.github/workflows/ci.yml`; alterar `B:pyproject.toml`, `B:tests/conftest.py`, `B:app/core/config.py`, `B:app/modules/{auth,public,maintenance}/router.py`, `F:package.json` e lockfile para Playwright dev; criar `B:docs/superpowers/validation/2026-10-21-piloto-aceite.md`.

**Interfaces:** fixtures descartáveis com `TEST_POSTGRES_URL`; factory de cenário cria pessoas, admin, oficina e veículo sem chamar endpoints de bypass de produto. Jornadas de navegador usam backend rodando e storage/provedor controlados apenas no processo de teste. Homologação remota de P05 fica separada das fixtures locais. A CI de cada repo testa seu conteúdo; o runner de aceite documenta os dois SHAs usados.

- [ ] Adicionar testes de upgrade desde `20260707_0004` com dados representativos, leitura de enums, documentos e manutenções legadas sem publicação automática. `test_acceptance_A01` a `test_acceptance_A20` registram o mapeamento das verificações já existentes e exercitam o que faltar; não criar vinte duplicatas que apenas repetem implementação. Navegador registra manutenção usando o mesmo endpoint/payload que a UI real.
- [ ] Executar testes direcionados e confirmar falhas das jornadas ainda incompletas; pré-condição de execução não conta como teste de produto falhando. Se não houver dependências ou banco, corrigir o ambiente autorizado e registrar o impedimento específico.
- [ ] Configurar CI com versões compatíveis com lockfiles, PostgreSQL descartável, lint, suites e build. Preservar a cadeia de migrações; corrigir incompatibilidades de defaults/enums por migração de compatibilidade com testes desde base antiga. Implementar `enforce_rate_limit(scope, identity, limit, window_seconds)` com contador Redis atômico e 429 com `Retry-After`: cadastro 5/h por IP; login 10/min por IP e identidade normalizada; recuperação 3/15min por identidade; consulta 60/min por IP; convite 10/h por responsável. Valores configuráveis; identidade não é registrada em claro. Testar limiar, reset e isolamento; indisponibilidade do contador retorna erro recuperável, não libera abuso silenciosamente. Documentar cada A01–A20 com teste/resultado, SHA e evidência sanitizada.
- [ ] Executar verificações completas P00, integração PostgreSQL e `npm run test:e2e` em F:. Executar também upgrade de base vazia e antiga e restauração de backup em banco de testes. Nenhum teste local de pagamento substitui homologação com Sandbox real.
- [ ] Commit sugerido em cada repo alterado: `test: verify complete pilot journeys and migrations`.

### Task 4 — T4: Preparação de disponibilização e acompanhamento

**Arquivos:** criar `B:Dockerfile`, `B:.dockerignore`, `B:docker-compose.pilot.yml`, `B:docs/superpowers/validation/2026-10-21-piloto-operacao.md`, `B:app/cli/pilot_report.py`; alterar `B:README.md`, `B:.env.example`, `B:app/api/v1/health.py`, `B:app/core/{config,logging}.py`, `B:.gitignore`; criar `F:Dockerfile`, `F:.dockerignore`, `F:nginx.conf`; alterar `F:README.md` ou criá-lo se inexistente.

**Interfaces:** `python -m app.cli.pilot_report --from YYYY-MM-DD --to YYYY-MM-DD` produz métricas agregadas de funil, tempo de análise, rejeições, duplicidade, disputa, completude de prazo/estrelas e compras de testes, sem dados pessoais. Configuração de piloto recusa chave JWT padrão, debug e gateway de produção. Health público não expõe credenciais; readiness verifica dependências sem incluir dados privados.

- [ ] Testar configuração piloto recusando valores inseguros e provedor de produção; relatório vazio não divide por zero; janela e amostras correspondem aos eventos persistidos. Build dos contêineres não incorpora `.env`, testes com dados privados ou diretórios `.git`.
- [ ] Executar teste de configuração/relatório e build local dos contêineres; falha deve apontar condição concreta, sem iniciar serviços externos ou publicar imagem.
- [ ] Escrever procedimento de bootstrap, migração única, worker, R2 privado/CORS do bucket, HTTPS no ponto de entrada e restauração. Capturador de e-mail é local; SMTP externo só após configuração autorizada. Roteiro cobre uma jornada de cada origem, cliente convidado, contestação, edição, compra com expiração e fim de assinatura. Abrir exceção no `.gitignore` somente para os dois documentos de validação deste plano.
- [ ] Registrar comandos/resultados e pendências operacionais no aceite. Preparar uma decisão concreta de implantação com ambiente e custos identificados; pedir autorização de publicação somente nesse ponto, sem executar deploy automaticamente. Prazos comerciais, retenção final, suporte e produção financeira continuam critérios de passagem ao MVP.
- [ ] Commit sugerido: `chore: prepare pilot operation and release evidence` em cada repo alterado.

**Saída:** evidências verificáveis de A01–A20, pendências operacionais explícitas e pacote de implantação revisável. Disponibilizar o piloto e ativar cobrança real são decisões distintas; este plano não liga produção financeira.
