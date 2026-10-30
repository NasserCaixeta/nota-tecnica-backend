# Vercel + VPS — implantação e operação

Data:30/10/2026. Implantação autorizada pelo usuário, execução direta na main e commits separados. Frontend mantido na Vercel; backend na VPS existente, sem contratar infraestrutura. Pagamentos desativados.

## Endereços e release

- Frontend: https://nota-tecnica-frontend.vercel.app
- API temporária: https://nota-tecnica-api.62-72-8-213.sslip.io
- Readiness: https://nota-tecnica-api.62-72-8-213.sslip.io/api/v1/ready
- VPS:62.72.8.213, Ubuntu24.04/x86_64; Nginx existente.
- Backend ativo:7a4ee334324e6dc08b00ea94bac4b1b8f7473ad9; imagem amd64 sha256:63868be7a64feb077a0200d6509c2a0fe6660f897e281fd3e6c2c8df75d7dec9.
- Frontend:31cd7f201c8d7d5eed5785598b6cec8aac65a07e, com configuração de publicação05a4388. A correção31cd7f2 altera somente teste.

`sslip.io` é endereço temporário dependente do IP e desse DNS público. Ao adotar domínio próprio, configurar DNS/certificado/vhost novo e atualizar o buildCommand em vercel.json. Ao trocar domínio do frontend, atualizar FRONTEND_URL, CORS e callback no ambiente privado e preparar outro release. Origem de preview não é liberada automaticamente.

## Isolamento e configuração

Projeto Compose `nota-tecnica-vps`, volumes/rede próprios, PostgreSQL16 e Redis7 sem portas públicas. API somente `127.0.0.1:18001`. Worker e beat separados, imagem igual à API. Banco `nota_tecnica_pilot`, head20261030_0018. Camelbox permanece com containers e configurações anteriores.

Arquivos em `/opt/nota-tecnica` com acesso root restrito. Releases imutáveis em `releases/<commit>`, symlink `current` aponta só para release verificado. Bootstrap privado em `shared/.env.vps`; release atual tem snapshot próprio `.env.vps`, modo0600, com NOTA_TECNICA_RELEASE igual ao código. Ao preparar próximo release, copiar configuração privada atual, ajustar só a tag e eventuais mudanças de configuração deliberadas; nunca imprimir o arquivo.

APP_ENV=pilot, DEBUG=false; JWT/convite/recuperação e senha do banco gerados no servidor, distintos. PAYMENTS_ENABLED=false, STRIPE_SECRET_KEY/WEBHOOK_SECRET vazios. A chave live local não foi enviada. R2 e SMTP não foram configurados nem reutilizados de outro projeto. Não iniciar um segundo projeto Compose apontando aos mesmos dados.

## Atualização e verificação

Enviar `git archive <commit>` para diretório novo dentro de releases, sem .git nem arquivos locais privados. Preparar `.env.vps`0600 para aquele release e tag. Nunca alterar a senha de um banco persistido apenas no arquivo: isso não muda a senha PostgreSQL existente.

```sh
sh /opt/nota-tecnica/releases/<commit>/deploy/vps-release.sh /opt/nota-tecnica/releases/<commit>
```

O script valida configuração, constrói imagem, preserva banco/Redis, executa migração isolada e só então substitui API/worker/beat sem repetir o serviço migrate. Falha de build/migração não remove aplicações anteriores. Migração precisa ser compatível com versão ainda ativa; há breve indisponibilidade durante troca de containers. Depois de sucesso/readiness, atualizar current. Não usar `down -v`, não trocar volumes e não fazer downgrade destrutivo para rollback. Falha de readiness após troca exige diagnóstico/correção ou retorno a uma imagem compatível com o schema aplicado.

```sh
cd /opt/nota-tecnica/current
docker compose --env-file .env.vps -f docker-compose.vps.yml ps
docker compose --env-file .env.vps -f docker-compose.vps.yml exec -T api python -m app.cli.pilot_report --from 2026-10-01 --to 2026-10-31
curl --fail --silent https://nota-tecnica-api.62-72-8-213.sslip.io/api/v1/ready
```

Nginx exclusivo em `/etc/nginx/sites-available/nota-tecnica-api`; exemplo versionado em deploy/nginx-api.conf.example. Certificado separado, expira28/01/2027; Certbot timer habilitado e hook `/etc/letsencrypt/renewal-hooks/deploy/nota-tecnica-nginx-reload` valida/recarrega apenas para esse certificado. Webroot `/var/www/nota-tecnica-acme`. Hook executado com sucesso; não foi necessário alterar certificado/vhost Camelbox. Headers XFF recebidos do cliente são sobrescritos. Logs de URL desativados; usar saúde, logs sanitizados de aplicação e relatório para diagnóstico.

## Evidência e pendências

HTTPS readiness200; pagamentosfalse; /users/me401 sem token. CORS origem Vercel permitido e origem estrangeira negada. Forjar XFF não cria outro orçamento de rate limit. Worker respondeu pong; beat rodando. Browser público consulta ranking por HTTPS sem erros no console. Vercel abre /entrar e /app/garagem; assets existentes200, ausentes404, bundle sem API localhost. Site/API Camelbox200 e mesmos containers; banco/Redis Nota Técnica preservados durante atualização.

352 testes backend com PostgreSQL/Redis/Docker passaram, Ruff check/format215arquivos. Duas regressões reais do deploy observaram RED→GREEN; não dependem de fixtures de dados da aplicação. Execução opt-in: TEST_DOCKER_DEPLOY=1 uv run pytest tests/integration/test_vps_release.py. Frontend69testes/lint/build; CI31cd7f2 passou após corrigir teste que preenchia select ainda desabilitado. Vercel deployment7446952549. Nenhum fluxo com documentos, e-mail ou pagamento real foi afirmado como homologado.

Backup inicial privado do banco: `/opt/nota-tecnica/backups/initial-20261030T192249Z-a80f26.dump`,122341bytes, SHA256a1a1f4a059af617d91b135ba6c685c87a70d3318d2cd15fbb2f55ad3e37d7c9e. Restaurado com pg_restore --no-owner --exit-on-error em banco novo exclusivo `nota_tecnica_restore_eff257dde0d8`, head0018 confirmado; banco ativo não foi sobrescrito/excluído. Metadados em shared/initial-backup.json. É cópia no mesmo disco, sem R2, sem backup externo ou rotina diária configurados.

Antes de liberar jornadas completas: configurar R2 privado/CORS e validar documentos; SMTP/remetente e entrega autorizada; primeiro administrador após usuário real cadastrado (CLI app.cli.bootstrap_admin); backup externo/agendamento/arquivos e responsáveis por suporte/moderação. Cobrança e integração Stripe de produção continuam fora desta implantação. Não existe conta administrativa fictícia criada pelo deploy.

## Revisão final

Revisor independente único, somente leitura, backend966053a..e2036f9/frontend367c731..05a4388. Nenhum Critical/Minor; um Important: compose up-d poderia remover serviços antigos antes de migração com falha. Resolvido em7a4ee33 com script fail-fast e migração isolada, regressões Docker reais para falha de build e de migração RED→GREEN, suíte352 aprovada. O fluxo corrigido foi usado com sucesso para atualizar a VPS. Sem segunda revisão.

CI backend [41115216770](https://github.com/NasserCaixeta/nota-tecnica-backend/actions/runs/41115216770) aprovada em7a4ee33; frontend [41115014912](https://github.com/NasserCaixeta/nota-tecnica-frontend/actions/runs/41115014912) aprovada em31cd7f2. A CI padrão pula os dois casos Docker opt-in; a suíte local352 os incluiu. Ambos os repositórios foram publicados na main. Relatórios/docs posteriores não alteram a imagem ativa.

O ledger completo, incluindo todos os pontos deixados pelo revisor para julgamento do executor e os custos das decisões, é preservado a seguir antes da remoção do workspace temporário.


## Ledger integral preservado

```text
# SDD ledger — plan: docs/superpowers/plans/2026-10-30-vercel-vps.md
Authorization: user chose Vercel frontend + own VPS and approved direct execution after read-only recon; prior main/separate commits persist. SSH password never stored in repo; authenticated control socket temporary only.
Pre-flight: T1 produces loopback API18001 and distinct release image; T2 host Nginx consumes same port and Vercel/CORS share exact HTTPS origins. T3 records release source SHAs, remote image ID and private backup location. No interface conflicts.
Ruling: use temporary hostname nota-tecnica-api.62-72-8-213.sslip.io while own domain not supplied; DNS resolves VPS and service permits ACME — cost: temporary external DNS dependency and IP embedded in hostname. Replace when own domain is configured.
Ruling: use direct HTTPS browser/API and explicit CORS rather than Vercel external rewrite, preserving direct client IP at Nginx for rate limits — cost: requires API HTTPS and exact frontend origin configuration.
Ruling: release env excludes local Stripe live credential and disables payments; R2/SMTP remain unconfigured until own credentials — cost: uploads/email/payment journeys are unavailable on deployed instance, not claimed ready.
Task1: no product code changed; configuration-only verification uses Compose validation/semantic ports and actual remote build/readiness instead of new mirrored tests. Source e2036f9, amd64 image sha256:6908521bb4be75e5d3e9d375db1ac820e574a96c5137698b555c68d7c6ef965e, migration0018 success, new services private, Camelbox existing IDs/health retained. Dedicated TLS certificate issued, expiration2027-01-28; no live payments enabled.
Task 1: complete (commits ba30e3e..e2036f9, tests: bash .superpowers/sdd/2026-10-30-vercel-vps/check-task1.sh → {"status":"ready"})
Task2: TLS separate certificate obtained with existing Certbot ACME account and webroot. Own vhost only, nginx-t before reload, Camelbox config byte-equal to initial snapshot. Renewal hook restricted to this certificate tested, certbot.timer enabled. HTTPSready200, protectedme401, configenabledfalse, exactoriginpreflight200/foreign400, ranking200. Forged XFF two values increment real loopback client Redis budget by2. Public Camelbox site/API200.
Task2: Vercel actual pre-change routes /entrar and /app/garagem404 and JSlocalhost API observed. Commit05a4388 deployed; actual routes now200, missingasset/API404, JavaScriptasset200 withHTTPS API and no localhost. Browser actual cross-origin ranking200/pilot_v1, console0errors. Frontend69/lint/build passed.
Task2: first remote CI05a4388 failed existing rating test interacting with disabled select before async initial GET finished; GitHub annotations named exact test. Fix test to await enabled state, no product behavior changed. Full69/lint/build GREEN; separatecommit31cd7f2 pushed, remote CI success41115014912 and Vercel deployment7446952549. No retry-only masking.
Final review: backend966053a..e2036f9/frontend367c731..05a4388, one reviewer read-only, one Important (up-d can remove old apps before migration succeeds), no Critical/Minor. Fix script staged fail-fast migration then no-deps application switch; actual isolated Docker probes old workflow RED2 (build/migration), new script GREEN2, complete backend352/352withPGRedisDocker, one upstream TestClient warning. Ruff215files/diffclean. Commit7a4ee33.
Ruling: staged migrations must remain compatible with old live API, and final container replacement has brief downtime — cost: this deployment is not zero-downtime and breaking migrations need an explicit later strategy. Build/migration failure preserves old API/worker/beat.
Ruling: request URL/error logging disabled in new vhost to avoid leaking tokens/PII; API sanitized class logs and readiness/report remain — cost: proxy-level request diagnostics are intentionally limited.
Task2: corrected script successfully used on VPS to build amd64 image63868be7a64feb077a0200d6509c2a0fe6660f897e281fd3e6c2c8df75d7dec9, migrate then replace apps and wait healthy; current changed only after success. Postgres/Redis original new-stack containers preserved, Camelbox unchanged. Live configuration snapshot mode0600, no local credentials copied. Worker ping pong1node, pilot report allzero confirms no synthetic participant creation.
Task 2: complete (commits e2036f9..7a4ee33, tests: .venv/bin/python .superpowers/sdd/2026-10-30-vercel-vps/check-public.py → PASS: HTTPS API, CORS, authorization, payments off, SPA routes/assets, HTTPS bundle, existing Camelbox)
Task3: initial database backup122341bytes mode0600 SHA256a1a1f4a059af617d91b135ba6c685c87a70d3318d2cd15fbb2f55ad3e37d7c9e restored into fresh exclusive nota_tecnica_restore_eff257dde0d8; head0018 verified; no active/preexisting DB overwritten/dropped. Backup metadata private on VPS; no R2 objects configured.
Final: Ruling: reviewer declined remote env/permissions — actual current.env0600, runtime pilot/debugfalse/paymentfalse/Stripeblank and image lacksenv/git verified; configuration remains private — cost: future manual edits require repeating these checks.
Final: Ruling: reviewer declined effective Camelbox isolation/health — same four container IDs and byte-equal original Nginx config verified, publicsite/API200; no shared volumes/networks introduced — cost: shared physical VPS still shares capacity/failure domain.
Final: Ruling: reviewer declined HTTPS/renewal — certificate issued and browser verified, dedicated renewal hook tested and timer enabled; no claim of observing a future renewal — cost: ongoing certificate expiration monitoring remains operational work.
Final: Ruling: reviewer declined production XFF/CORS — actual spoofed XFF counter and exact/foreign preflights passed; reject previews/customorigins by default — cost: new frontend hostname must be configured explicitly.
Final: Ruling: reviewer declined Vercel deployment/reload/assets — real published deep routes200/missingassets404 and browsercrossorigin200/console0 verified; direct protectedgarage correctly redirectslogin — cost: this does not replace user-facing journeys requiring R2/SMTP/admin.
Final: Ruling: reviewer declined backup initial/restore — dump restored to fresh dedicated DB without clean/drop, schemahead verified; localdisk database-only backup, no offsite schedule promised — cost: machine loss still loses that local backup, and future files require own backup.
Final: Ruling: reviewer declined R2/SMTP/payments/bootstrapadmin/externalbackup — retain explicitly unavailable/pending, no fake participants/admin and no production financial activation — cost: deployment is reachable, but those full participant journeys are not yet operational.
Final: fixed Important migration-safety — test_failed_release_preserves_running_api[migration/build] both observed old workflowRED then stagedscriptGREEN; complete backend352/352withPGRedisDocker. No deferred Minor findings. One independent review, one fix pass, no re-review.
Final: remote CI backend41115216770 success on7a4ee33; frontend41115014912 success on31cd7f2. Public Vercel7446952549 success. Backend defaultCI skips opt-in Docker probes; full352local explicitly enabled them. Both mains pushed. Remote workerpong, reportzero syntheticusers, APIhealthy; current release7a4ee33.
Task 3: complete (commits 7a4ee33..7a4ee33, tests: .venv/bin/python .superpowers/sdd/2026-10-30-vercel-vps/check-public.py → PASS: HTTPS API, CORS, authorization, payments off, SPA routes/assets, HTTPS bundle, existing Camelbox)
```
