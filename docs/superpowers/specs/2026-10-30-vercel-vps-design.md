# Implantação Vercel + VPS existente

Usuário autorizou manter frontend na Vercel e backend na VPS existente, forneceu acesso SSH e confirmou execução direta após inspeção. Main e commits separados continuam autorizados. Escopo: implantar o código atual, sem habilitar pagamentos.

## Arquitetura e escolhas
Frontend existente https://nota-tecnica-frontend.vercel.app. API temporária https://nota-tecnica-api.62-72-8-213.sslip.io (hostname de DNS público derivado do IP, escolha do executor enquanto não há domínio próprio informado). Nginx existente termina TLS e sobrescreve headers de encaminhamento; acesso direto navegador→API HTTPS, CORS restrito ao frontend. Vercel recebe endereço público de API no build e fallback SPA; nenhuma credencial em VITE.

VPS Ubuntu24.04/x86_64, Docker Compose já disponível. Camelbox existente permanece em seus serviços/redes/volumes/portas. Nota Técnica usa projeto Compose nota-tecnica-vps, API publicada só127.0.0.1:18001, PostgreSQL/Redis privados, worker e beat únicos, diretório /opt/nota-tecnica e releases imutáveis por commit. Nginx recebe somente novo vhost; validar antes de reload e preservar configuração anterior. Certbot webroot para certificado separado, sem editar vhosts Camelbox.

## Alternativas consideradas
Stack toda na VPS conflita com escolha explícita da Vercel. Publicar API HTTP por IP impede chamada segura do frontend HTTPS. Domínio próprio seria preferível quando disponível; hostname sslip.io permite HTTPS agora sem registro/DNS adicional, com dependência temporária desse serviço.

## Configuração e limites
Gerar segredos JWT/convite/recuperação e senha de banco distintos na VPS; .env.vps privado0600, nunca copiar credencial Stripe live local. PAYMENTS_ENABLED=false e chaves Stripe vazias. APP_ENV=pilot/DEBUG=false, CORS/frontend/callback HTTPS explícitos. R2 e SMTP não configurados permanecem pendentes e não serão anunciados como funcionais. Não reutilizar dados/credenciais Camelbox. Sem contratação, cobrança real ou envio de email.

## Aceite
API readiness HTTPS200 com Postgres/Redis, pagamentos desabilitados, endpoints autenticados protegidos, preflight CORS permitido só origem configurada e XFF forjado sobrescrito. SPA /entrar e /app/garagem resolvem, bundle usa API HTTPS, frontend consegue consultar endpoints públicos. Camelbox continua saudável. Migração0018 aplicada no banco próprio. Segredos fora dos commits/imagem/logs. Backup inicial privado de banco e instruções de restauração; backup externo/arquivos/R2/SMTP/bootstrap admin dependem da etapa operacional correspondente.
