# Prévia e ranking explicável — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or, if chosen by the user, superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Expor prévia sem dados privados e classificar oficinas por serviços elegíveis, com fórmula reproduzível.

**Architecture:** Usar a seleção canônica de P03 para toda agregação pública. Definir projeção pública independente da resposta privada de manutenção. Calcular inicialmente sob demanda para evitar cache desatualizado depois de contestação.

**Tech Stack:** Stack existente; Decimal para cálculo e pytest/Vitest para valores de referência.

**Spec:** [Seções 6, 7 e 9; A13, A18–A20](../specs/2026-10-21-piloto-nota-tecnica-design.md).

## Global Constraints

Aplicam-se P00–P03. Sem histórico completo de terceiros até P05. Preço e retrabalho não entram na pontuação. `pilot_v1`, escala 0–10, pesos 40/40/20, volume saturado em vinte e posição apenas com cinco serviços e pelo menos um componente de qualidade presente.

## Review Focus

- Placa privada com serviço pendente não revela existência nem se distingue de placa sem histórico público; T1.
- Descrição/arquivo de serviço não é reutilizado diretamente em projeção pública; T1.
- Autoavaliação, avaliação duplicada e avaliação de revisão antiga não contribuem; T2.
- Prazo ausente não se transforma em pontualidade perfeita; filtros recalculam amostras; T2.
- Contestação deve alterar o ranking e a prévia na chamada seguinte; T1/T2/T3.

### Task 1 — T1: Prévia e projeção sanitizada de manutenção

**Arquivos:** alterar `B:app/modules/public/{schemas,service}.py`, `B:app/modules/maintenance/schemas.py`; criar `B:app/modules/maintenance/projections.py`, `B:tests/test_public_history_privacy.py`; ajustar `B:tests/test_public_history_preview.py`; alterar `F:src/features/public/{pages/PlateSearchPage.tsx,components/HistoryPreviewPanel.tsx}`, `F:src/lib/api/public.ts` e seus testes.

**Interfaces:** `PublishedMaintenanceRead` contém só identificador do serviço, data, odômetro, categoria/sistema, `public_description`, oficina pública e custos; nunca identidade pessoal, documentos, chassi ou Renavam. `build_published_maintenance_read(record, revision, workshop) -> PublishedMaintenanceRead`. Manter rota de prévia existente e seu envelope, com `vehicle_found` refletindo disponibilidade pública, não cadastro privado.

- [x] Testar que veículo conhecido sem serviço elegível e placa desconhecida têm prévia neutra equivalente, salvo a própria placa. Testar serialização: `assert private_fields.isdisjoint(payload.keys())`; inserir CPF/endereço na descrição privada e garantir que só `public_description` aprovada aparece. Contestação reduz contagem e altera datas imediatamente.
- [x] Executar `uv run pytest tests/test_public_history_privacy.py tests/test_public_history_preview.py -q`; confirmar falhas dos novos casos.
- [x] Implementar agregações com P03, somente campos permitidos; não devolver lista de serviços no endpoint público. Não cobrar nem oferecer compra quando não houver histórico. Interface explica que a prévia não é relatório completo e que o checkout será de testes quando P05 estiver disponível.
- [x] Executar testes direcionados e testes da página pública em F:, incluindo falha de rede e placa inválida sem resultado anterior enganoso.
- [x] Commit sugerido: `fix: expose only eligible vehicle history previews`.

### Task 2 — T2: Avaliação vinculada e fórmula versionada

**Arquivos:** criar `B:app/modules/ranking/{reviews,scoring}.py`, `B:alembic/versions/20261021_0011_service_reviews.py`, `B:tests/{test_service_reviews,test_pilot_ranking}.py`; alterar `B:app/modules/ranking/{service,schemas,router}.py`, `B:app/modules/maintenance/router.py` e `B:app/db/base.py`.

**Interfaces:** `PUT /maintenance-records/{id}/review` recebe `revision_id`, `stars` 1–5 e comentário opcional; restrição única por manutenção/cliente, com versão associada. `PilotScoreInput(service_count: int, average_stars: Decimal | None, measured_deadlines: int, on_time_count: int)` e `calculate_pilot_score(data) -> PilotScore(score: Decimal | None, eligible_for_ranking: bool, sample_label: str)` em `scoring.py`. Resposta publica contagens por componente, versão e explicação.

- [x] Testar `N=10`, quatro estrelas, 8/10 no prazo: `assert result.score == Decimal('7.4')`; sem estrelas, prazo 8 e volume 5: `assert result.score == (Decimal('.4')*8 + Decimal('.2')*5)/Decimal('.6')`. Com `N=0`, sem nota/posição; `N=4`, amostra pequena; `N=5` só com volume, sem nota/posição. Nota inválida 0/6 retorna 422; responsável pela própria oficina recebe 403; revisão antiga não contribui.
- [x] Executar `uv run pytest tests/test_service_reviews.py tests/test_pilot_ranking.py -q`; confirmar falhas esperadas.
- [x] Calcular Decimal sem arredondar antes da ordenação; retornar nota exibida com uma casa decimal. Usar recorte cidade/UF/categoria antes das agregações. Excluir referência não verificada, serviço secundário associado e revisão contestada. Avaliação é opcional e editável pelo cliente, com auditoria; administrador modera comentário sem mudar estrelas. Empate usa volume e ID estável.
- [x] Executar testes de fórmula, avaliação e ranking existentes; conferir alteração imediata após disputa e reconfirmação. Não quebrar cálculo por número nulo ou lista sem prazos.
- [x] Commit sugerido: `feat: add verified service reviews and pilot ranking`.

### Task 3 — T3: Perfil, filtros, indicadores e landing com dados reais

**Arquivos:** alterar `F:src/lib/api/ranking.ts`, `F:src/features/public/pages/WorkshopRankingPage.tsx`, `F:src/features/workshops/{components/WorkshopRankingCard.tsx,components/WorkshopRankingList.tsx,pages/WorkshopProfilePage.tsx}`, `F:src/features/public/components/landing/FeaturedWorkshopRanking.tsx`, `F:src/content/landing.ts`; criar `F:src/features/public/pages/WorkshopRankingPage.test.tsx` e `F:src/features/workshops/pages/WorkshopProfilePage.test.tsx`; ajustar testes existentes da landing.

**Interfaces:** página aceita cidade, UF e categoria e envia os mesmos filtros ao endpoint; cards recebem `score: number | null`, `eligible_for_ranking`, `sample_label`, `review_count`, `measured_deadline_count`, versão e explicação. Perfil mostra indicadores e avaliações publicáveis, sem nomes pessoais dos avaliadores. Expor no backend `GET /public/workshops/{id}/performance` com a mesma regra de elegibilidade de T2.

- [x] Testar oficina sem serviços sem nota inventada; amostra quatro sem posição; mudança de filtro atualiza a amostra e mantém contexto. Landing sem dados mostra vazio honesto; falha de API mostra erro recuperável. Não renderizar taxas de retrabalho fixas nem avaliações de serviço contestado.
- [x] Executar em F: `npm run test -- --run src/features/public src/features/workshops`; confirmar falha dos novos comportamentos.
- [x] Substituir dados estáticos por consulta real, mantendo eventual exemplo explicitamente rotulado e fora do ranking. Usar perfil conectado de P03; mostrar fórmula legível, versão e contagens. Avaliação parte do detalhe do serviço reconhecido, não de botão público irrestrito.
- [x] Executar verificações completas P00 e simular retirada de um serviço por contestação, conferindo landing, prévia, perfil e ranking na próxima leitura.
- [x] Commit sugerido em cada repo alterado: `feat: show transparent pilot workshop performance`.

**Saída:** prévia e ranking confiáveis sem acesso completo gratuito; P05 usa `PublishedMaintenanceRead` na consulta comprada.
