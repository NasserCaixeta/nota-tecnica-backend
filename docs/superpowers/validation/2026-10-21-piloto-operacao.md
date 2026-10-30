> Atualizado em30/10/2026: provedor substituído por Stripe. [Configuração e evidências atuais](2026-10-30-stripe.md). Relatórios P05/P06 anteriores preservam o histórico da implementação.

# Operação proposta do piloto — 28/10/2026

Pacote local preparado para revisão; nenhum recurso remoto foi contratado, publicado ou configurado nesta execução. Pagamentos continuam exclusivamente Sandbox e desligados por padrão. [Aceite e par de commits](2026-10-21-piloto-aceite.md).

## Decisão concreta proposta

Um VPS x86 Linux em Helsinki, classe Hetzner CX33, com Docker Compose, Postgres16, Redis7, API, worker, um beat e Nginx/SPA. TLS termina em Caddy no host, encaminhando apenas para `127.0.0.1:8088`. Banco, Redis e API não publicam portas. R2 separado e privado guarda comprovantes. Este é um piloto de baixo volume em uma máquina, sem alta disponibilidade; disponibilidade/capacidade precisam ser medidas antes do MVP.

Referência de custos consultada em 28/10/2026: CX33 €8,49/mês, sem IPv4 e impostos, na [tabela oficial Hetzner](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/). Disponibilidade da classe é confirmada no provisionamento. Reservar orçamento de €20/mês para computação/IPv4/backup é uma estimativa de planejamento, não cotação nem autorização de gasto; domínio, SMTP, impostos/câmbio e armazenamento externo ficam à parte.

R2 Standard tem franquia mensal de 10GB-mês, 1 milhão de operações A e 10 milhões B; além disso, US$0,015/GB-mês, US$4,50/milhão A e US$0,36/milhão B. Conferir arredondamentos e uso na [documentação oficial de preços R2](https://developers.cloudflare.com/r2/pricing/). Não presumir gratuidade ilimitada. SMTP comercial e destino independente de backup ainda precisam de escolha/cotação autorizada; o capturador local não envia e-mail aos participantes.

A proposta depende da aceitação da região dos dados, domínio e responsável técnico. Nenhum prazo de disponibilidade/suporte ou retenção definitiva foi contratado. A publicação depende de autorização operacional explícita posterior; produção financeira continua uma decisão separada.

## Configuração privada

Manter os dois repositórios irmãos no mesmo host, fixados no par de SHAs aprovado. Criar `.env.pilot` fora do Git, permissões0600, a partir de `.env.example`. O arquivo é lido pelo Compose e pelos processos, nunca entra na imagem. Não executar `docker compose config` sem `-q` em logs compartilhados: pode expandir segredos.

Preencher, antes de inicializar:

- `APP_ENV=pilot`, `DEBUG=false`; `JWT_SECRET_KEY`, `INVITATION_SECRET_KEY`, `RECOVERY_SECRET_KEY` com três valores aleatórios distintos de pelo menos32 caracteres. Gerar cada um em gerenciador de segredos ou `openssl rand -hex 32`; não colar em tickets.
- `PILOT_DB_PASSWORD` aleatória e `DATABASE_URL=postgresql+asyncpg://nota_tecnica:<senha-url-encoded>@postgres:5432/nota_tecnica_pilot`. O valor codificado deve corresponder à senha literal do Postgres. `REDIS_URL=redis://redis:6379/0`.
- `FRONTEND_URL=https://<dominio-piloto>`, `BACKEND_CORS_ORIGINS=["https://<dominio-piloto>"]`.
- `PAYMENTS_ENABLED=false`, `PAYMENTS_ENVIRONMENT=sandbox`. Não incluir chave de produção. Para homologação autorizada: preços explícitos, chave secreta de teste, STRIPE_WEBHOOK_SECRET fornecido pelo endpoint Stripe e callback HTTPS. Só ativar após roteiro P05; retorno de checkout nunca concede benefício.
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL` com credencial limitada ao bucket privado do piloto.
- `SMTP_ENABLED=false`, `SMTP_CAPTURE_ONLY=true` no primeiro boot. Para capturador autorizado local: `SMTP_ENABLED=true`, `SMTP_HOST=mailpit`, `SMTP_PORT=1025`, profile `mail`. A UI Mailpit fica apenas no loopback, acessível por túnel administrativo. SMTP externo exige credenciais, remetente e autorização próprios; nesse momento usar TLS, `SMTP_CAPTURE_ONLY=false` e repetir teste com destinatário autorizado.

## Bootstrap e implantação após autorização

Os comandos deste roteiro são instruções para uma implantação futura, não evidência de execução remota. Não usar `docker compose down -v` em operação.

```sh
docker compose --env-file .env.pilot -f docker-compose.pilot.yml config -q
docker compose --env-file .env.pilot -f docker-compose.pilot.yml build
docker compose --env-file .env.pilot -f docker-compose.pilot.yml up -d postgres redis
docker compose --env-file .env.pilot -f docker-compose.pilot.yml run --rm migrate
docker compose --env-file .env.pilot -f docker-compose.pilot.yml up -d api worker beat frontend
```

`migrate` executa Alembic uma vez por liberação antes dos consumidores. Não escalar migrate/beat e não iniciar migrações em todos os workers. O `depends_on` também impede API/worker/beat de iniciar antes de migrate concluído. Fixar imagem por digest no release e guardar par de SHAs/digests; build local atual é nativo ARM, VPS proposto é x86 e precisa de build linux/amd64 na CI/host antes do rollout.

Instalar Caddy no host autorizado e configurar DNS do domínio. Exemplo de Caddyfile, substituindo o domínio:

```caddyfile
pilot.example.com {
    reverse_proxy 127.0.0.1:8088
}
```

Liberar apenas80/443 ao público e SSH restrito a administradores; não expor8088,5432,6379,8000 ou Mailpit. Antes dos participantes, identificar o endereço real do proxy visto pelo Nginx (normalmente gateway da rede Docker) e definir `PILOT_TRUSTED_PROXY=<ip-exato>/32` em `.env.pilot`, recriando frontend. Confiar só nesse salto, nunca `0.0.0.0/0`. Verificar com duas origens controladas que o rate limit usa IP distinto e que header `X-Forwarded-For` forjado é sobrescrito. O padrão confia apenas em loopback; sem este ajuste, todos podem compartilhar orçamento por IP. Não colocar API em rede acessível a contêineres não confiáveis: Uvicorn confia no Nginx interno.

Após HTTPS, registrar a primeira conta pelo formulário (continua pendente), conferir identidade operacional e promover somente a primeira administração pelo CLI:

```sh
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec api python -m app.cli.bootstrap_admin --email <email-operador>
```

O CLI exige conta existente ativa, registra auditoria e recusa se já houver administrador aprovado ativo. Demais administradores passam pela interface com auditoria; não editar privilégios direto no banco.

## Bucket e navegador

Desligar acesso público/r2.dev e não associar domínio público de arquivos. Separar bucket/credenciais de outros ambientes. O servidor assina PUT temporário, inspeciona bytes e copia evidência aceita para chave imutável; download exige remetente/admin e expira em300s. Bucket não substitui autorização da API.

Exemplo de política para o domínio exato (adaptar no painel; não aplicado nesta execução):

```json
[{
  "AllowedOrigins": ["https://pilot.example.com"],
  "AllowedMethods": ["PUT", "GET", "HEAD"],
  "AllowedHeaders": ["Content-Type"],
  "ExposeHeaders": ["ETag"],
  "MaxAgeSeconds": 600
}]
```

URLs assinadas usadas no navegador também exigem CORS, conforme a [documentação oficial R2](https://developers.cloudflare.com/r2/buckets/cors/). Testar upload PDF e imagem, arquivo inválido, expiração e negação de documento alheio. Nunca registrar URL assinada, conteúdo bruto, CPF ou token. Não criar lifecycle que remova `verified/` antes de uma política de retenção aprovada.

## Saúde, fila e acompanhamento

`GET /health` é liveness sem I/O; `/api/v1/ready` verifica Postgres e Redis, com timeout e503 neutro. Readiness não comprova R2, SMTP ou Stripe. Verificar esses adaptadores por jornada autorizada; não bloquear liveness por serviço externo.

API/worker usam a mesma imagem/configuração; beat dispara recuperação de notificações e pagamentos a cada60s. Outbox permanece no banco se broker/SMTP falha; não repetir aprovação nem criar nova compra para resolver fila atrasada. Acompanhar `notification_deliveries` pendentes/failed, `payment_events` e `checkout_events` pendentes, pedidos `reconciliation_required` e cancelamentos. Não copiar payloads para monitoramento. Celery registra WARNING; API e proxy sem accesslog e erro de aplicação só informa classe, sem traceback com parâmetros SQL. Logs locais rotacionam10MBx3 por processo configurado; destino/alertas remotos ainda dependem de operação.

```sh
docker compose --env-file .env.pilot -f docker-compose.pilot.yml ps
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec api python -m app.cli.pilot_report --from 2026-10-01 --to 2026-10-31
```

Relatório retorna somente agregados: participantes/criação/aprovação, vínculos, oficinas, serviços/publicação atual, submissões/duplicidade/disputas, tempo médio e amostra de revisão, rejeições, completude de prazo/estrelas e pedidos Sandbox por estado. Janela é UTC, ambas as datas inclusivas. Coorte reflete estado atual das entidades criadas na janela; não é snapshot histórico. Tempo usa submissão e decisão da mesma revisão, inclusive submissão anterior à janela. Eventos legados sem revision_id não recebem tempo inventado; amostra vazia produz null. Completude usa publicação canônica atual e avaliação da revisão corrente.

Administradores acompanham a fila de solicitações de identidade/encerramento. O sistema registra pedido privado e auditável, sem apagar histórico nem trocar CPF automaticamente. Antes de executar tratamento manual, definir responsável, canal de resposta e política aplicável; não prometer encerramento já realizado ao receber pedido.

## Backup e restauração

Proposta operacional inicial: backup diário cifrado, cópia fora do VPS, retenção técnica provisória de7diários+4semanais, acesso administrativo restrito; confirmar retenção final antes dos participantes. RPO alvo24h e RTO alvo4h são objetivos a medir, sem SLA validado. Backup do banco não contém os objetos R2: copiar também objetos e manifesto de chaves/ETags para destino independente e testar a leitura de documentos restaurados.

Dump manual em diretório administrativo protegido, com nome novo (bash/zsh, sem sobrescrever):

```sh
umask 077
set -C
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec -T postgres pg_dump -U nota_tecnica -Fc nota_tecnica_pilot > backup-<timestamp-unico>.dump
```

Copiar/cifrar para destino autorizado, verificar tamanho/hash e status do comando. Não presumir que arquivo existente significa dump íntegro. Ensaio de restauração **sempre em banco novo**, criado explicitamente com nome exclusivo; pg_restore sem `--clean`, sem DROP e com `--exit-on-error`:

```sh
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec -T postgres createdb -U nota_tecnica restore_<id_unico>
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec -T postgres pg_restore -U nota_tecnica --no-owner --exit-on-error -d restore_<id_unico> < backup-<timestamp-unico>.dump
```

Comparar head Alembic, contagens, vínculos, documentos e auditoria; apontar instância isolada ao banco restaurado e storage copiado, sem SMTP/webhooks/beat externos. Só migrar tráfego para restauração após verificação e autorização. Não restaurar por cima do banco ativo nem fazer downgrade destrutivo para reverter aplicação. Para rollback, preservar dump e imagem anterior compatível; correção de esquema é uma decisão própria.

O teste local `tests.integration.backup_roundtrip` já comprovou roundtrip de dados sintéticos com bases novas; não substitui ensaio do bucket e do ambiente remoto.

## Roteiro operacional antes dos participantes

1. Cadastrar conta, ver pendência/403, aprovar por outro administrador e conferir auditoria/notificação; recuperar senha e verificar sessão antiga rejeitada, sem mudar aprovação.
2. Validar primeiro veículo com comprovante; cliente registra manutenção, envia evidência e submete; só publicar depois da revisão do documento e serviço.
3. Responsável por oficina registra serviço para cliente convidado; convite não aprova conta nem vínculo. Resolver identidade/participação/vínculo, reconhecer revisão exata e conferir publicação única.
4. Contestar serviço confirmado: retirar publicação/ranking imediatamente. Editar informação relevante e exigir nova revisão/reconhecimento. Associar duplicidade sem duplicar contagem.
5. Prévia neutra e histórico sem arquivo/PII. Em Sandbox real, retorno forjado não libera; evento confirmado duplicado concede uma janela de720horas. Validar novas aprovações durante janela e negação no vencimento com relógio de testes, sem editar datas do banco operacional.
6. Assinatura confirmada oferece5vagas totais; cancelamento preserva período pago. No fim, adicionais mantêm leitura e atos de reconhecimento/contestação, mas novos lançamentos diretos são bloqueados. Não esperar30dias reais: usar cenários de tempo controlado e registrar separadamente eventos reais do provedor.
7. Interromper SMTP/broker em ambiente de homologação, conferir persistência da decisão/outbox e recuperação; restaurar dump/bucket em destino novo e registrar tempos.

## Evidência local desta entrega

Builds backend/frontend concluídos. Smoke temporário validou imagem API sem debug, readiness com PostgreSQL/Redis reais, rota SPA profunda, proxy HTTP da API e CLI agregado. Contextos Docker são allowlists, sem .env/.git/testes; imagem API foi inspecionada para confirmar ausência desses caminhos. Recursos temporários foram removidos; nenhuma imagem foi publicada. Resultados completos e revisão ficam no aceite e relatório P06.

Pendentes externos: domínio/conta/servidor e autorização de publicação; R2 privado/CORS real; SMTP/backup externo; teste de confiança do proxy no host escolhido; build x86; homologação financeira Stripe de testes e período/cancelamento; definição de retenção, suporte, preços e critérios do MVP comercial. Não ativar cobrança real como parte do piloto.
