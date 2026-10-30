# Vercel + VPS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Usuário optou por execução direta na main, com commits separados, e autorizou implantação nesta VPS.

**Goal:** Disponibilizar backend isolado na VPS e conectar frontend Vercel existente.
**Architecture:** Compose separado; Nginx host com TLS; frontend usa API HTTPS direta e fallback SPA.
**Tech Stack:** Docker Compose, PostgreSQL16, Redis7, FastAPI/Celery, Nginx/Certbot, Vite/Vercel.
**Spec:** ../specs/2026-10-30-vercel-vps-design.md

## Global Constraints
Não alterar Camelbox; segredos somente privados; API loopback18001; Postgres/Redis sem portas; pagamentos desabilitados; origens HTTPS explícitas; nenhuma promessa de R2/SMTP sem credencial.

## Review Focus
- Cliente forja XFF: Nginx deve sobrescrever e manter IP real para rate limit.
- Deploy novo deve preservar volumes e nunca fazer down-v ou restaurar sobre banco ativo.
- Rotas SPA profundas e arquivos estáticos da Vercel funcionam após reload.
- Credencial Stripe live local não é copiada e não bloqueia configuração remota.
- Falha de build/migração impede substituir configuração ativa; Camelbox permanece saudável.

### Task 1: Pacote backend isolado
Files: docker-compose.vps.yml, deploy/nginx-api.conf.example, README.md.
Interfaces: .env.vps privado consumido por Compose; NOTA_TECNICA_RELEASE nomeia imagem; API loopback18001.
- [ ] Criar Compose sem frontend, com API/worker/beat/migrate e banco/Redis próprios; preservar healthcheck/migrate gate/log rotation.
- [ ] Criar modelo Nginx com TLS separado, XFF sobrescrito, logs sem URLs, cache privado e limites.
- [ ] Validar docker compose config-q com ambiente sintético privado; build linux/amd64 na VPS e readiness interno com banco migrado. Commit separado.
Expected: apenas API expõe loopback18001, seis serviços, env validado sem segredo no output.

### Task 2: HTTPS e Vercel
Files F: vercel.json, README.md; B:docs/superpowers/validation/2026-10-30-vercel-vps.md.
Interfaces: frontend build VITE_API_BASE_URL=https://nota-tecnica-api.62-72-8-213.sslip.io/api/v1; CORS somente frontend estável.
- [ ] Novo vhost HTTP serve somente ACME, obter cert separado com webroot, ativar HTTPS após nginx-t; renovar com reload.
- [ ] Configuração Vercel define build da API pública e fallback SPA, sem segredo nem proxy intermediário.
- [ ] Frontend lint/test/build; publicar commits e verificar GitHub/Vercel status e paths reais. API HTTPS/CORS/health/autorização/XFF e Camelbox verificados.
Expected: readiness200, frontend público e paths SPA200, origem não autorizada sem ACAO, pagamentos false.

### Task 3: Operação e fechamento
Files: README e relatório docs/superpowers/validation/2026-10-30-vercel-vps.md.
- [ ] Registrar par de commits, configuração de release, backup privado inicial e restauração em banco novo; pendências R2/SMTP/admin/backup externo.
- [ ] Revisão independente única dos arquivos alterados; corrigir Important/Critical e verificar; commits separados e relatório final com ledger preservado.
Expected: estado remoto comprovado, segredos ausentes do Git, limites externos explícitos.
