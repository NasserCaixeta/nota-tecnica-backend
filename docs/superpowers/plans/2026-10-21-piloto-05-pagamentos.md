# Compra de histórico e assinatura de testes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or, if chosen by the user, superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validar compra por placa de 30 dias e assinatura mensal de cinco veículos, sem cobrança real.

**Architecture:** Separar pedido, evento financeiro e benefício. Usar adaptador de provedor, processamento transacional idempotente e autorização calculada pelo servidor em cada leitura. O frontend acompanha o pedido; não concede benefícios.

**Tech Stack:** Stack existente, cliente HTTP assíncrono e Asaas Sandbox como escolha técnica proposta; testes locais usam gateway controlado, não simulam homologação remota concluída.

**Spec:** [Seções 4.4, 7 e 8; A04, A06 e A13–A17](../specs/2026-10-21-piloto-nota-tecnica-design.md).

## Global Constraints

Aplicam-se P00–P04. Somente participantes aprovados compram. Assinatura e acesso por placa são produtos distintos. Histórico válido por 720 horas; assinatura segue períodos mensais confirmados, não intervalos inventados de trinta dias. Nunca receber dados de cartão no backend da aplicação.

## Review Focus

- URL de retorno adulterada, pagamento de outro usuário ou valor divergente não concede acesso; T1/T2/T3.
- Reentrega, eventos invertidos, reinício do worker e confirmação duplicada não duplicam benefícios; T2.
- Expiração exata, timezone e confirmação recebida com atraso não estendem a compra indevidamente; T2/T3.
- Cancelamento, falha de renovação e reversão preservam dados sem liberar seis vagas; T3.
- Falta de conta/chave do provedor não pode ser reportada como homologação realizada; T1/T4.

## Escolha do provedor e fontes

Propor **Asaas Sandbox com checkout hospedado**, porque permite concentrar compra avulsa e recorrência num adaptador sem coletar cartão na aplicação. É uma escolha para implementação do piloto, não contratação comercial nem criação de conta já autorizada. Se o usuário preferir outro provedor antes de T1, preservar o contrato abaixo e revisar só o adaptador e a homologação.

A documentação oficial descreve [checkout hospedado e modalidades](https://docs.asaas.com/docs/checkout-asaas), [ambiente de testes separado](https://docs.asaas.com/docs/sandbox), [criação de checkout](https://docs.asaas.com/reference/criar-novo-checkout), [recorrência](https://docs.asaas.com/docs/checkout-with-subscription-recurring), [autenticação de webhooks](https://docs.asaas.com/docs/about-webhooks), [eventos de cobrança](https://docs.asaas.com/docs/webhook-para-cobrancas) e [idempotência](https://docs.asaas.com/docs/como-implementar-idempotencia-em-webhooks). Consultadas em 21/10/2026; conferir novamente os contratos de payload ao executar T1.

Pré-requisitos da homologação remota: conta Sandbox, chave exclusiva, token de webhook distinto da chave da API e URL HTTPS de testes para retorno dos eventos. Solicitar apenas os dados que ainda faltarem ao chegar nessa etapa; nunca gravar credenciais em plano, teste ou commit. As tarefas de domínio podem avançar com gateway controlado enquanto a homologação estiver pendente.

### Task 1 — T1: Pedido persistido e adaptador de checkout

**Arquivos:** criar `B:app/modules/payments/{models,schemas,service,router,gateway}.py`, `B:app/integrations/payments/{__init__,asaas}.py`, `B:alembic/versions/20261021_0012_payments_orders.py`, `B:tests/{test_checkout_orders,test_asaas_gateway}.py`; alterar `B:app/api/v1/router.py`, `B:app/db/base.py`, `B:app/core/config.py`, `B:.env.example`, `B:pyproject.toml` e lockfile apenas para promover a dependência HTTP necessária a runtime.

**Interfaces:** `PaymentProduct` com `history_access` e `garage_monthly`; `PaymentOrder` guarda comprador, produto, placa/veículo quando aplicável, preço/moeda imutáveis, ambiente, IDs do provedor e estado. `PaymentGateway.create_checkout(order: CheckoutOrder) -> CheckoutSession(provider_id, url)` e `fetch_payment(provider_payment_id: str) -> ProviderPayment`; tipos definidos em `gateway.py`. `POST /payments/history-checkouts` recebe placa; `POST /payments/subscription-checkouts` não recebe preço nem limite; `GET /payments/orders/{id}` só para comprador/admin.

- [ ] Testar preço vindo do servidor apesar de JSON manipulado; placa sem histórico publicável não gera checkout; conta pendente recebe 403; comprador B não lê pedido de A. Gateway timeout não marca pago; retry do mesmo pedido usa a mesma referência e não cria benefício. Asserts: `assert granted_count == 0`, `assert order.currency == 'BRL'`.
- [ ] Executar `uv run pytest tests/test_checkout_orders.py tests/test_asaas_gateway.py -q`; confirmar falhas de comportamento.
- [ ] Criar pedido antes do contato externo; manter mapeamento de IDs retornados e política de retry com reconciliação, sem criar pedidos substitutos silenciosos. Adaptador usa host Sandbox fixado por configuração validada, checkout avulso e recorrente mensal conforme documentação atual. Preços de teste precisam de configuração explícita em centavos e rótulo de simulação; ausência torna compra indisponível com mensagem clara. Nenhum segredo vai para frontend ou logs.
- [ ] Executar testes do gateway com respostas oficiais sanitizadas e HTTP controlado; rejeitar host de produção quando `APP_ENV` for piloto/teste. Conferir que criação/retorno do checkout nunca concede benefício.
- [ ] Commit sugerido: `feat: create sandbox history and subscription checkouts`.

### Task 2 — T2: Webhook autenticado, confirmação e períodos

**Arquivos:** criar `B:app/modules/payments/{webhooks,events,benefits}.py`, `B:app/integrations/queue/payment_tasks.py`, `B:alembic/versions/20261021_0013_payment_benefits.py`, `B:tests/{test_payment_webhooks,test_payment_benefits}.py`, `B:tests/integration/test_payment_concurrency.py`; alterar `B:app/modules/payments/{models,router}.py` e `B:app/integrations/queue/celery_app.py`.

**Interfaces:** `POST /payments/webhooks/asaas` recebe evento autenticado; `PaymentEvent` único por `(provider, environment, event_id)`; `process_payment_event(session, event_id: int, gateway, now: datetime) -> None`. `HistoryAccessGrant` único por pedido, com `starts_at` e `expires_at`. `SubscriptionPeriod` único por cobrança confirmada, com início/fim mensais. Eventos persistem antes do HTTP 200 e são processados por ID, sem segredos no broker.

- [ ] Testar token ausente/incorreto retorna 401 sem evento; duplicata autenticada retorna 200 com `assert event_count == 1`. Confirmações distintas da mesma cobrança geram `assert grant_count == 1`; acesso começa na confirmação financeira verificada, com `assert expires_at - starts_at == timedelta(hours=720)`. Evento atrasado não ganha 30 dias novos a partir do recebimento. Divergência de valor/moeda/comprador mantém pedido sem benefício e sinaliza reconciliação.
- [ ] Executar `uv run pytest tests/test_payment_webhooks.py tests/test_payment_benefits.py -q`; confirmar falhas esperadas.
- [ ] Validar `asaas-access-token` com comparação segura e segredo próprio, não chave da API. Recuperar estado financeiro canônico do provedor antes de aplicar mudanças; evento de checkout sozinho não prova pagamento. Inserir benefício e marcar processamento na mesma transação, com índices únicos. Evento de confirmação seguido de estorno, ou estorno entregue antes de confirmação, converge para estado canônico. Worker reconsulta eventos persistidos pendentes após reinício; teste local pode invocar o mesmo processador diretamente, sem endpoint para “marcar pago”.
- [ ] Executar testes direcionados e concorrência PostgreSQL com eventos simultâneos; simular crash entre persistir evento e despachar tarefa e recuperar sem duplicar. Testar restituição/reversão revogando somente benefício correspondente.
- [ ] Commit sugerido: `feat: apply verified payment events idempotently`.

### Task 3 — T3: Direito por placa e limite comercial da garagem

**Arquivos:** criar `B:app/modules/payments/access.py`, `B:app/modules/public/history.py`, `B:tests/{test_paid_history_access,test_garage_subscription}.py`; alterar `B:app/modules/public/router.py`, `B:app/modules/garage/{policy,router,schemas}.py`, `B:app/modules/payments/{service,router}.py`.

**Interfaces:** `has_history_access(session, user_id: int, vehicle_id: int, now: datetime) -> bool`; `GET /history/vehicles/{plate}` exige participante e vínculo ativo ou compra válida e usa `PublishedMaintenanceRead` de P04 para acesso de terceiros. `get_garage_capacity` de P02 passa a ler períodos confirmados; `PATCH /garage/free-vehicle` recebe `vehicle_id`; `POST /payments/subscriptions/{id}/cancel` solicita cancelamento e mantém período já confirmado. Oficina continua restrita aos próprios serviços por suas rotas.

- [ ] Testar um instante antes/depois e exatamente no vencimento: `now < expires_at` autoriza, `now == expires_at` não. Compra de outra placa/conta não autoriza. Documento bruto, CPF e Renavam nunca aparecem na consulta comprada. Com assinatura, cinco veículos podem escrever e sexto não; após vencer, somente o gratuito escreve, adicionais legitimados continuam legíveis. Contestação e reconhecimento de serviço da oficina seguem permitidos sem assinatura.
- [ ] Executar `uv run pytest tests/test_paid_history_access.py tests/test_garage_subscription.py -q`; confirmar falhas dos novos direitos.
- [ ] Aplicar decisões no servidor em cada chamada, sem depender de job de expiração. Impedir segunda compra enquanto acesso vigente; assinatura não concede acesso a veículo sem vínculo. Cancelamento remoto persistido não concede período novo; reconciliação corrige falhas transitórias. Seleção gratuita só aceita vínculo vigente do usuário e deixa primeira inclusão válida como padrão. Preservar dados e leitura dos adicionais; não restaurar uma sexta vaga ao renovar.
- [ ] Executar testes de direitos, garagem, rotas antigas e concorrência de alocação; verificar acesso atualizado a novo serviço aprovado dentro do período.
- [ ] Commit sugerido: `feat: enforce paid history access and garage subscription capacity`.

### Task 4 — T4: Checkout, assinatura e histórico na interface

**Arquivos:** criar `F:src/lib/api/payments.ts`, `F:src/features/payments/pages/{CheckoutStatusPage,SubscriptionPage}.tsx`, `F:src/features/public/pages/PaidVehicleHistoryPage.tsx` e testes junto às páginas; alterar `F:src/features/public/pages/PlateSearchPage.tsx`, `F:src/features/garage/pages/{GarageDashboardPage,AddGarageVehiclePage}.tsx`, `F:src/lib/api/garage.ts`, `F:src/app/router.tsx`.

**Interfaces:** `/app/compras/:orderId` consulta estado do servidor; `/app/assinatura` mostra ciclo, até cinco vagas e cancelamento; `/app/historico/:plate` lê a rota protegida de T3. Retorno do checkout só informa ID opaco do pedido para acompanhar. UI mostra “Ambiente de testes — sem cobrança real”, preço configurado e validade antes de redirecionar.

- [ ] Testar retorno `?status=paid` com pedido pendente: não renderiza histórico. Testar pagamento recusado/retry, compra vigente sem novo checkout, vencimento durante uso, cancelamento com período restante e seleção de veículo gratuito. UI nunca aceita preço/quantidade enviada pelo usuário como configuração financeira.
- [ ] Executar em F: `npm run test -- --run src/features/payments src/features/public/pages/PaidVehicleHistoryPage.test.tsx`; confirmar falhas esperadas.
- [ ] Conectar pedido, acompanhamento com polling limitado e opção de atualizar, histórico e capacidade comercial; não ocultar 403 como lista vazia. Aguardar webhook antes de mensagem de liberação. Não enviar e-mails reais, criar conta financeira ou publicar ambiente neste passo sem autorização operacional correspondente.
- [ ] Executar verificações completas P00. Com credenciais próprias de Sandbox e URL de testes já autorizada, homologar checkout avulso, recorrência, evento duplicado, rejeição, cancelamento e reversão; anexar IDs sanitizados e resultados ao registro de homologação. Se faltarem credenciais, registrar homologação remota pendente, sem substituí-la pelos testes locais.
- [ ] Commit sugerido em cada repo: `feat: connect sandbox purchases and garage subscription`.

**Saída:** regras comerciais testadas e integração remota comprovada ou explicitamente pendente. Nenhuma cobrança real é ativada.
