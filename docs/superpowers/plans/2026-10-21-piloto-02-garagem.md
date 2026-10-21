# Garagem, legitimidade e documentos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or, if chosen by the user, superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validar vínculos, impedir acesso por placa declarada e tornar documentos verificáveis e privados.

**Architecture:** Separar vínculo documental de ocupação da garagem; centralizar capacidade e autorização. Todos os uploads passam por inspeção no armazenamento antes de satisfazer requisitos. Reutilizar o serviço de auditoria de P01.

**Tech Stack:** Stack existente, boto3/R2, testes com storage controlado e PostgreSQL para concorrência.

**Spec:** [Seções 4, 10, 12; A04–A07 e A20](../specs/2026-10-21-piloto-nota-tecnica-design.md).

## Global Constraints

Aplicam-se P00 e P01. Uma vaga gratuita real antes de P05; nenhuma assinatura de demonstração no servidor. Vínculo validado autoriza leitura própria, nunca arquivos de outro remetente.

## Review Focus

- Duas criações simultâneas por rotas diferentes não obtêm duas vagas gratuitas; T1.
- Mesma placa não libera histórico ou dados pessoais; divergência de identificadores não sobrescreve veículo; T1.
- Outro remetente com vínculo na mesma placa não confirma/lê o documento; T2.
- PUT falhou, objeto não existe, tipo real diverge ou tamanho excede limite: requisito não satisfeito; T2/T3.
- Documento rejeitado e reenvio não herdam aprovação; revisão concorrente recebe 409; T3.

### Task 1 — T1: Vínculo separado de vaga e autorização de histórico

**Arquivos:** alterar `B:app/modules/vehicles/{models,service,schemas}.py`, `B:app/modules/garage/{service,schemas}.py`, `B:app/modules/maintenance/service.py`, `B:app/modules/admin/service.py`; criar `B:app/modules/vehicles/access.py`, `B:app/modules/garage/policy.py`, `B:alembic/versions/20261021_0006_garage_membership.py`, `B:tests/test_vehicle_access.py`, `B:tests/integration/test_garage_concurrency.py`; ajustar `B:tests/{test_vehicles,test_garage,test_garage_admin}.py`.

**Interfaces:** `require_active_vehicle_link(session, user_id: int, vehicle_id: int) -> VehicleUser`; `GarageCapacity` contém `limit: int`, `free_vehicle_id: int | None`, `writable_vehicle_ids: set[int]`; `get_garage_capacity(session, user_id: int, now: datetime) -> GarageCapacity`. `VehicleUser` mantém relação documental; `GarageMembership` guarda inclusão para gestão; `User.free_garage_vehicle_id` aponta para a seleção gratuita. Rota antiga chama o mesmo caso de uso de criação, adaptando a resposta.

- [ ] Adicionar testes: criar primeiro veículo por `/vehicles`, segundo por `/garage/vehicles` não libera dois para escrita; cliente B vincula placa de A e `assert history.status_code == 403` antes de aprovação; dados públicos/privados de A não aparecem na resposta do pedido de B; divergência de chassi/Renavam retorna 409 sem sobrescrita. Dois pedidos simultâneos deixam `assert writable_count == 1`.
- [ ] Executar `uv run pytest tests/test_vehicle_access.py tests/test_garage.py -q`; confirmar falhas esperadas.
- [ ] Unificar criação e verificação de duplicidade, serializando alocação de vagas por usuário. Migrar estados documentais sem confiar em `payment_required`; registrar vínculos desse estado como pendentes sem escrita. Migrar inclusões existentes sem liberar todas: escolher a primeira gratuita e adicionais em leitura, preservando dados. Bloquear histórico anterior quando vínculo pendente; permitir somente próprios rascunhos. Rótulos de compartilhar/relatório continuam falsos, pois estão fora do piloto. Revogação retira leitura sem apagar dados.
- [ ] Executar testes de acesso, garagem e concorrência PostgreSQL; testar migração e comprovar que um vínculo usado só para reconhecimento não exige vaga comercial.
- [ ] Commit sugerido: `fix: enforce vehicle legitimacy and shared garage limits`.

### Task 2 — T2: Upload inspecionado e leitura privada

**Arquivos:** alterar `B:app/integrations/storage/r2.py`, `B:app/modules/documents/{models,schemas,service,router}.py`, `B:app/core/config.py`, `B:app/modules/garage/router.py`; criar `B:app/modules/documents/access.py`, `B:tests/test_document_privacy.py`; ajustar `B:tests/{test_documents,test_integrations}.py`.

**Interfaces:** `StorageClient.inspect_object(storage_key: str) -> StoredObjectInfo(exists: bool, size_bytes: int, content_type: str)`; `StorageClient.create_presigned_download_url(storage_key: str, expires_seconds: int) -> str`; `get_document_download(session, document_id, actor, storage) -> DocumentDownloadRead(url: str, expires_at: datetime)`. `GET /documents/{id}/download` só retorna URL após conferir remetente/admin; auditoria da leitura administrativa usa P01.

- [ ] Testar documento enviado por A na placa compartilhada: B recebe 404 em leitura/confirmar/download; A e admin autorizados recebem URL com `expires_at = now + 300s`. Objeto inexistente ou maior que `10 * 1024 * 1024` não passa a `uploaded`. Arquivo com tipo real incompatível é rejeitado, mesmo com cabeçalho declarado permitido.
- [ ] Executar `uv run pytest tests/test_document_privacy.py tests/test_documents.py -q`; os casos novos devem falhar na implementação atual.
- [ ] Exigir inspeção via HEAD e amostra controlada do conteúdo para reconhecer os quatro formatos aceitos; timeout/erro de storage deixa o upload pendente e retorna erro recuperável. Não aceitar `storage_key` arbitrária no endpoint legado: remover sua concessão de `uploaded` e responder 410 apontando ao fluxo de intenção. Respostas comuns não expõem chave de storage. Persistir intenção antes de gerar URL e registrar falha/retry sem marcar sucesso. Verificação final controla upload excessivo mesmo se o cliente contornar a validação prévia.
- [ ] Executar testes direcionados e testes de storage; testar repetição de confirmação sem duplicar decisões, logs sem URL assinada e ausência de acesso público ao bucket na homologação posterior.
- [ ] Commit sugerido: `fix: inspect uploads and authorize private document reads`.

### Task 3 — T3: Checklist, análise de vínculo e experiência completa

**Arquivos:** alterar `B:app/modules/garage/{service,schemas}.py`, `B:app/modules/admin/{router,service}.py`, `B:tests/{test_garage,test_garage_admin}.py`; criar `B:tests/test_vehicle_review_versions.py`; alterar `F:src/lib/api/{garage,documents,admin,types}.ts`, `F:src/features/garage/pages/{GarageVehicleDocumentsPage,GarageVehicleDetailPage,AddGarageVehiclePage}.tsx`, `F:src/features/admin/pages/AdminValidationDetailPage.tsx`, `F:src/features/garage/components/{DocumentChecklist,GarageAddVehicleForm}.tsx`; criar testes correspondentes `GarageVehicleDocumentsPage.test.tsx` e `AdminValidationDetailPage.test.tsx` junto às páginas.

**Interfaces:** checklist informa `missing_uploads`, `awaiting_review`, `rejected` e `approved` por tipo. Enviar para análise exige uploads verificados dos tipos exigidos; ativar vínculo exige aprovação documental de todos esses tipos. `PATCH /admin/garage/vehicle-links/{id}/review` recebe `expected_version`; `GET /admin/garage/vehicle-links/{id}` permite detalhe direto, não reconstrução a partir da fila. Reenvio mantém histórico e invalida aprovação do arquivo substituído.

- [ ] Testar: upload sem aprovação permite submeter à fila, mas não ativar; documento rejeitado bloqueia ativação; correção cria nova análise; admin não aprova próprio vínculo; duas decisões com mesma versão geram 200 e 409. Frontend com PUT 403 não chama confirmação; PUT bem-sucedido atualiza checklist e envia análise real.
- [ ] Executar `uv run pytest tests/test_vehicle_review_versions.py -q`; em `F:`, executar os testes novos de documentos e detalhe administrativo; confirmar falhas de comportamento.
- [ ] Conectar seleção de arquivos, PUT, verificação de `response.ok`, confirmação e envio/reenvio à API. Tela administrativa abre documentos por URL privada e decide com versão/motivo. Remover botão local de “fluxo preparado”. Exibir dados conflitantes como pendência sem revelar outros vínculos, preservar erros e permitir retry.
- [ ] Executar verificações completas de P00 e jornada cadastro → CRLV → análise documental → vínculo ativo, incluindo solicitação de documento adicional.
- [ ] Commit sugerido em cada repo: `feat: complete garage document validation journey`.

**Saída:** garagem e análise documental utilizáveis; privacidade exercitada antes de adicionar operação de oficinas em P03.
