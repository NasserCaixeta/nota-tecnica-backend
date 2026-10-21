# Spec de produto e arquitetura — piloto Nota Técnica

Data: 21/10/2026.

Estado: aprovada pelo usuário em 21/10/2026, após apresentação do arquivo e resposta “mete bronca”. Implementação ainda não iniciada.

Abrangência: backend `nota-tecnica-backend` e frontend irmão `nota-tecnica-frontend`.

Próxima etapa: revisão desta spec, seguida de planos de implementação por subsistema.

## 1. Objetivo e origem das decisões

Entregar um piloto utilizável por clientes e oficinas para validar cadastro, legitimidade do vínculo com veículos, histórico documentado, confirmação dos atendimentos e ranking explicável. O piloto deve exercitar também compras e assinatura em ambiente de testes, preparando a passagem para o MVP comercial.

A aprovação dos participantes será manual, embora o cadastro seja aberto. O sucesso do piloto será demonstrado por jornadas reais concluídas e dados rastreáveis; o número de telas prontas não é critério de conclusão.

Esta spec usa o diagnóstico dos repositórios e a documentação original como contexto. Para o piloto, as decisões abaixo substituem as partes conflitantes da visão original, especialmente o ranking e a monetização da garagem. Não pressupõe que o código atual já satisfaça essas regras.

### 1.1. Decisões aprovadas na conversa

| Tema | Regra aprovada |
| --- | --- |
| Público | Clientes e oficinas participam do mesmo piloto. |
| Entrada | Cadastro aberto; operação depende de aprovação administrativa. |
| Administração | Vários administradores, todos com os mesmos poderes e ações auditadas. |
| Conta | Uma conta pode ser cliente e responsável por oficina. |
| Oficina | Aprovação independente da aprovação da pessoa. |
| Veículo | Vínculo documental validado antes de acessar histórico anterior. |
| Origem do serviço | Cliente ou oficina, inclusive oficina atendendo cliente sem conta. |
| Evidência | Comprovante obrigatório nas duas origens. |
| Moderação | Todos os registros de manutenção passam por análise administrativa no piloto. |
| Reconhecimento | Autoria do cliente reconhece seu lançamento; lançamento da oficina exige confirmação do cliente. |
| Contestação | Análise administrativa, com publicação e contribuição no ranking bloqueadas durante a disputa. |
| Alteração | Mudança relevante exige nova análise e, para origem oficina, nova confirmação. |
| Privacidade | Documentos pessoais não entram na prévia nem no histórico comprado. |
| Consulta | Prévia pública; histórico completo de terceiros apenas mediante compra. |
| Compra | Acesso ao histórico atualizado de uma placa por 30 dias após confirmação do pagamento. |
| Cobrança no piloto | Checkout, assinatura e confirmação em ambiente de testes, sem cobrança real. |
| Garagem | Primeiro veículo gratuito; um plano mensal permite até 5 veículos no total. |
| Fim da assinatura | Dados preservados, adicionais em leitura e novos lançamentos bloqueados; usuário escolhe o veículo gratuito. |
| Ranking | Prazo, avaliação de 1 a 5 estrelas e quantidade de serviços confirmados, com indicação de amostra pequena. |
| Integridade do ranking | Responsáveis não avaliam a própria oficina; serviços contestados não contribuem. |

### 1.2. Como ler as propostas complementares

Os detalhes marcados **Proposta para revisão** foram apresentados como propostas na versão submetida ao usuário. O aceite do documento os incorpora como referência inicial do piloto. A marcação foi preservada para distinguir sua origem das decisões discutidas individualmente. Estão reunidos também na seção 16.

A escolha de provedor de pagamentos, valores comerciais e serviços externos de e-mail pertence ao desenho técnico e à preparação comercial. Esta spec define os comportamentos que qualquer integração escolhida deve cumprir.

## 2. Limites do piloto

### 2.1. Incluído

- Conta com participação aprovada, sessão, saída e recuperação de acesso.
- Conta com capacidades de cliente e responsável por oficina, sem cadastros pessoais duplicados.
- Garagem, checklist de documentos, validação administrativa e leitura do histórico próprio.
- Cadastro e reivindicação de oficina por CNPJ, com análise da representação.
- Registro de manutenção nas duas origens, comprovantes, confirmação, correções e contestação.
- Convite para cliente ainda sem conta e associação segura ao atendimento.
- Painel administrativo para participantes, vínculos, oficinas, comprovantes e contestações.
- Prévia por placa, compra de 30 dias e assinatura mensal em ambiente de testes.
- Perfil e ranking de oficinas com dados reais e explicação dos indicadores.
- Notificações das ações necessárias, trilha de auditoria e medição das jornadas.
- Aplicação utilizável em celular e desktop, com erros, vazios e carregamento tratados.

### 2.2. Fora do piloto

- Cobrança real, preços comerciais definitivos e operação financeira de produção.
- OCR obrigatório ou aprovação automática de documentos.
- Pontuação por preço, detecção automática de retrabalho e inteligência preditiva.
- Orçamentos, agendamento, pagamento do serviço automotivo e marketplace.
- Integrações com ERP, seguradoras, vistoriadoras ou bases externas de veículos.
- Relatório de venda exportável, compartilhamento público de histórico completo e documentos mascarados para compradores.
- Organização de frotas, equipes com permissões distintas e planos comerciais adicionais.

O comprovante do serviço automotivo e o pagamento de acesso à plataforma são conceitos distintos. A plataforma não processará o pagamento do reparo no piloto.

## 3. Pessoas, capacidades e aprovações

### 3.1. Conta pessoal

A pessoa mantém uma única identidade, com CPF e e-mail únicos. Ser responsável por oficina acrescenta uma capacidade, sem retirar o acesso de cliente. Aprovação da pessoa, atividade da conta, administração, vínculos com veículos e representação de oficinas são dimensões independentes.

Uma conta aguardando aprovação pode entrar, completar o perfil, acompanhar o pedido e corrigir pendências. Não pode operar garagem, publicar serviços, administrar oficina ou comprar acesso ao histórico.

**Proposta para revisão — estados da participação:** `pending`, `approved`, `rejected`, `suspended`. Rejeição e suspensão exigem motivo; correção e reenvio preservam o histórico de decisões. Suspensão bloqueia operações autenticadas de produto, inclusive acessos pagos, até regularização; não exclui registros.

### 3.2. Administração

Todos os administradores têm os mesmos poderes sobre as filas, contestações e acesso administrativo. Nenhum formulário público permite tornar-se administrador. Concessão e revogação registram quem agiu, quem recebeu a alteração, quando ocorreu e a justificativa.

**Proposta para revisão — integridade administrativa:** provisionar o primeiro administrador por mecanismo operacional restrito; impedir a remoção ou desativação do último administrador ativo; impedir que uma pessoa aprove sua própria participação, oficina ou vínculo veicular. Essas restrições são iguais para todos, sem criar um nível superior de administrador.

Cada decisão usa a versão atual do pedido. Duas análises concorrentes não podem sobrescrever silenciosamente uma à outra.

### 3.3. Oficina

A pessoa aprovada pode solicitar cadastro ou reivindicar oficina existente. O CNPJ identifica uma única oficina. Um cadastro feito por cliente é uma referência de estabelecimento, sem conceder representação.

**Proposta para revisão — representação:** o administrador confere os dados do CNPJ e a documentação do representante antes de liberar operação. A oficina só ganha perfil público operacional após aprovação; referências ainda não verificadas podem aparecer no registro de manutenção, identificadas dessa forma, sem posição no ranking.

Reivindicar um CNPJ existente cria um pedido de representação, sem duplicar a oficina ou transferir sua gestão automaticamente. A aprovação da conta não aprova a oficina; a aprovação da oficina não valida qualquer veículo.

## 4. Garagem e vínculo com veículo

### 4.1. Identidade e cadastro

A placa normalizada identifica o veículo na base do piloto. Cadastrar uma placa existente cria um pedido de vínculo com o mesmo veículo; não recria a entidade, não altera seus dados para todos e não revela seu histórico anterior.

Dados divergentes, como chassi ou Renavam já cadastrados, devem gerar pendência para análise, sem sobrescrita silenciosa. A busca por placa consulta os dados internos; o piloto não promete consulta a uma base externa oficial.

O limite de garagem vale para todas as entradas da API, inclusive rotas antigas. A criação simultânea de veículos não pode liberar duas vagas gratuitas.

### 4.2. Evidência do vínculo

Manter os relacionamentos existentes, com documentos pessoais restritos ao remetente e à administração:

| Relação | Evidências mínimas |
| --- | --- |
| Proprietário | CRLV. |
| Cônjuge ou familiar | CRLV, autorização do proprietário e comprovação da relação. |
| Representante de empresa | CRLV, contrato ou procuração e identidade do representante. |
| Responsável pela frota | CRLV, autorização da frota e identidade do representante. |
| Comprador recente | CRLV e recibo de compra ou ATPV. |
| Condutor autorizado | CRLV, autorização e identidade do condutor. |
| Outro | CRLV e autorização, com justificativa para análise. |

O administrador pode pedir documentos adicionais, rejeitar com motivo ou aprovar. Arquivo enviado e documento aprovado têm significados diferentes. Documento rejeitado não satisfaz uma exigência aprovada.

### 4.3. Estados e permissões

Separar validação do vínculo da capacidade comercial. `payment_required` pode continuar sendo um rótulo de interface, mas não deve substituir o estado documental.

**Proposta para revisão — transições:** `pending_documents → under_review → active`; análise também pode retornar para `pending_documents` ou terminar em `rejected`. Reenvio após correção retorna a `under_review`. Revogação administrativa retira a condição `active`, com motivo e auditoria.

| Situação | O que o cliente pode fazer |
| --- | --- |
| Documentos pendentes ou em análise | Ver o próprio pedido e seus próprios rascunhos/lançamentos; enviar evidências quando permitido. |
| Vínculo ativo e vaga liberada | Consultar histórico próprio, registrar manutenção e confirmar atendimentos atribuídos corretamente. |
| Vínculo ativo e adicional sem assinatura | Consultar histórico; novos lançamentos diretos ficam bloqueados. |
| Vínculo rejeitado ou revogado | Consultar a decisão e corrigir pendências; sem acesso ao histórico anterior por esse vínculo. |

**Proposta para revisão — lançamento antecipado:** permitir que o cliente prepare manutenção e comprovantes antes da aprovação do veículo, mas só envie o registro para moderação após vínculo ativo e vaga liberada. Isso evita publicação de registros apoiados apenas em uma placa declarada.

Vínculo ativo permite a consulta própria sem compra por placa. Vínculo pendente não permite usar um convite para contornar essa validação.

### 4.4. Vaga gratuita e assinatura

Sem assinatura, uma vaga é gratuita. O plano mensal libera cinco no total, não cinco adicionais. Solicitar o sexto veículo deve explicar o limite e preservar os dados já informados, sem ativar uma sexta vaga.

**Proposta para revisão — fim do benefício:** cancelamento mantém benefícios até o fim do período já confirmado; ausência de renovação encerra o benefício no vencimento. O usuário pode indicar antecipadamente o veículo gratuito. Se não escolher, permanece gratuito o primeiro vínculo vigente da garagem, com possibilidade de trocar a seleção depois.

Veículos adicionais continuam legíveis apenas enquanto o vínculo documental for válido. A assinatura não substitui autorização documental e sua ausência não apaga o histórico.

**Proposta para revisão — limites da restrição:** o bloqueio comercial impede novas manutenções criadas diretamente pelo cliente nos adicionais. Não impede contestar registros, corrigir documentação solicitada, nem responder a um serviço já registrado por oficina. A oficina continua podendo registrar seus próprios atendimentos; isso não cria vaga paga na garagem do cliente.

Reconhecer um atendimento pode usar um vínculo validado específico, sem exigir inclusão em uma vaga de gestão da garagem. Esse vínculo permite reconhecer ou contestar o atendimento, mas não libera novos lançamentos diretos fora do limite comercial. A relação documental e a ocupação de vaga precisam ser representadas separadamente.

## 5. Manutenção, evidências e versão publicada

### 5.1. Dados e origem

Cada manutenção identifica placa/veículo, origem, autor, oficina quando conhecida, data do serviço, quilometragem, categoria, sistema do veículo, descrição, custo de peças e custo de mão de obra. O total é calculado pela aplicação. Datas de entrada, promessa e entrega efetiva são opcionais e alimentam o indicador de prazo somente quando suficientes.

Valores e quilometragem não podem ser negativos. Datas de entrega não podem anteceder a entrada. Informação ausente não deve ser convertida em zero, pontualidade perfeita ou avaliação positiva.

**Proposta para revisão — comprovante:** aceitar nota fiscal, ordem de serviço ou recibo que permita relacionar atendimento, veículo e prestador. Foto isolada do veículo, orçamento sem comprovação de execução e comprovante genérico sem identificação suficiente não bastam por si só. O administrador pode solicitar complemento.

As evidências devem ser inspecionadas manualmente para todas as manutenções. O cadastro do arquivo, sua existência no armazenamento e a decisão sobre seu conteúdo são etapas distintas.

### 5.2. Aprovação e confirmação independentes

Separar pelo menos estas dimensões, evitando um único estado ambíguo:

| Dimensão | Estados propostos |
| --- | --- |
| Fluxo editorial | `draft`, `submitted`, `cancelled`. |
| Análise administrativa | `pending`, `changes_requested`, `approved`, `rejected`. |
| Reconhecimento do cliente | `author_acknowledged`, `awaiting_customer`, `confirmed`, `disputed`. |
| Disputa | sem disputa, aberta ou encerrada, com resolução auditada. |

Para origem cliente, a autoria constitui reconhecimento da versão enviada. Para origem oficina, a confirmação é ato explícito do cliente legitimamente vinculado. Aprovação administrativa e confirmação podem ocorrer em qualquer ordem; a publicação depende das duas condições aplicáveis à mesma versão.

**Regra de publicação:** registro enviado, vínculo do cliente que o reconhece ativo, comprovante aceito, análise aprovada, reconhecimento válido e nenhuma disputa aberta. Para origem oficina, sua representação operacional deve estar aprovada no envio; uma suspensão posterior impede novos envios e provoca análise dos registros afetados, sem apagar automaticamente serviços legítimos passados.

### 5.3. Cliente ainda sem conta

A oficina aprovada pode criar atendimento pela placa sem afirmar quem é proprietário. Os dados informados pela oficina para o convite ficam privados e limitados ao necessário para contato.

**Proposta para revisão — convite:** link opaco, revogável, de uso único e com validade de sete dias, sem CPF ou placa expostos na URL. O cliente precisa autenticar-se, ser aprovado no piloto e validar seu vínculo com o veículo. Ter o link ou controlar o e-mail de destino, isoladamente, não libera histórico nem comprova propriedade.

O convite não aprova a pessoa, não aprova o veículo e não confirma o serviço automaticamente. Reenvio substitui o link anterior. Se não houver resposta, o serviço permanece pendente e não participa das métricas públicas.

### 5.4. Duplicidade

Uma manutenção real deve aparecer uma única vez no histórico e no ranking, mesmo se iniciada pelas duas partes. Ao encontrar possível correspondência por veículo, oficina, data e identificação do comprovante, oferecer associação ao registro existente.

**Proposta para revisão — associação:** duplicidade é uma sugestão sujeita a confirmação dos envolvidos ou do administrador. Não mesclar automaticamente serviços apenas por placa e data. Ao associar, preservar autores, documentos e versões; confirmação se refere a uma versão única do serviço.

Sugestões exibidas a cliente ou oficina só podem usar dados aos quais aquele ator já tenha acesso. Correspondências com registros privados de outro remetente são resolvidas pela administração, sem revelar seu conteúdo na busca.

### 5.5. Alterações

Mudança em veículo, oficina, datas, quilometragem, categoria, descrição do atendimento, valores ou comprovantes constitui alteração relevante. Cria nova versão, nova análise e, na origem oficina, nova confirmação do cliente.

**Proposta para revisão — publicação durante revisão:** retirar temporariamente o registro da prévia, do histórico comprado e do ranking até a nova versão cumprir as condições. Os envolvidos e administradores continuam vendo as versões. Isso torna inequívoco qual versão está aprovada.

## 6. Contestação e avaliações

O cliente pode contestar um serviço atribuído ao seu veículo, informando motivo e anexando evidências opcionais. A contestação abre uma fila administrativa e suspende imediatamente a publicação e a contribuição do serviço e da avaliação no ranking.

O administrador pode pedir informações, solicitar correção, encerrar como recusado ou registrar uma solução aceita pelas partes. Aprovação administrativa não transforma recusa do cliente em confirmação. Uma versão corrigida pela oficina só publica depois de nova confirmação.

**Proposta para revisão — contestação posterior:** permitir disputa mesmo após confirmação anterior. Uma disputa encerrada preserva sua decisão; a reabertura exige nova justificativa e é auditada. Oficinas podem apresentar resposta e evidências, mas não apagar a contestação.

Cada serviço elegível aceita uma avaliação do cliente reconhecedor, de 1 a 5 estrelas. Comentário é opcional. A avaliação pertence ao serviço, não é uma avaliação solta da oficina.

Qualquer pessoa com vínculo de responsabilidade com a oficina, inclusive por outra conta identificada da mesma pessoa, fica impedida de avaliá-la. Administrador pode moderar conteúdo inadequado com justificativa; não escolhe uma nota em nome do cliente.

**Proposta para revisão — serviço sem estrelas:** avaliação é opcional. O serviço continua contando no volume e, se tiver datas suficientes, no prazo; ausência de avaliação não equivale a cinco estrelas. Mudança relevante no serviço torna sua avaliação anterior inelegível até o cliente reconfirmá-la para a nova versão.

## 7. Consulta pública e histórico comprado

### 7.1. Prévia

A prévia pública considera somente registros publicáveis. Mostra quantidade de serviços, datas inicial/final, categorias e quantidade de oficinas. Placa sem registros publicáveis recebe resposta neutra de ausência de histórico disponível, mesmo que haja cadastros privados ou pendências.

Não revela existência de conta, vínculos pendentes, identidade de clientes, contato privado, dados documentais nem detalhes dos serviços. O botão de compra explica exatamente a duração e a natureza do acesso.

### 7.2. Conteúdo liberado

Compra confirmada concede ao comprador aprovado leitura por placa durante 30 dias corridos a partir do instante de confirmação, medido no servidor em UTC: 720 horas, sem depender de virada do mês ou horário de verão. O histórico é atualizado: novos registros elegíveis aparecem durante a validade. No instante do vencimento, deixa de existir autorização de leitura de terceiros.

Mostrar datas, quilometragem, categoria, descrição adequada à consulta, oficina e valores separados. Não mostrar nome, CPF, endereço, contato de proprietários/clientes, chassi, Renavam, documentos de vínculo ou arquivos brutos de comprovantes. Campos livres precisam passar por conferência de exposição de dados pessoais antes da publicação.

Comprar acesso não cria vínculo com o veículo, não permite alterar serviços, não concede documentos e não altera limites de garagem. Ter o veículo na garagem com vínculo ativo evita a necessidade dessa compra própria.

**Proposta para revisão — compra repetida:** enquanto há acesso válido, direcionar para o histórico existente e impedir checkout acidental duplicado. Após vencimento, uma nova compra inicia outros 30 dias. Não haverá renovação automática da consulta por placa.

Se não houver histórico disponível, explicar a ausência e não oferecer compra. Se um registro deixar de ser elegível durante a validade, removê-lo da consulta e manter o prazo do acesso; a compra não congela registros contestados.

## 8. Pagamento e assinatura em ambiente de testes

Existem dois produtos distintos: acesso por placa por 30 dias e assinatura mensal para cinco veículos. Uma compra não implica a outra. Valores de testes são configuráveis e exibidos antes de iniciar checkout; a interface identifica claramente que não há cobrança real no piloto.

A aplicação cria o pedido no servidor e usa a confirmação autenticada do provedor para conceder benefícios. Retorno ao frontend, parâmetro de URL ou pedido marcado pelo navegador nunca liberam acesso.

Eventos de pagamento precisam tolerar entrega duplicada, atraso, erro temporário e ordem invertida. O mesmo evento não cria dois acessos, duas assinaturas ou períodos adicionais. Pedido cancelado ou pagamento recusado não libera benefícios.

**Proposta para revisão — ciclo:** assinatura pendente não libera as vagas; período confirmado libera até sua data final. Falha de renovação não estende o benefício. Cancelamento encerra a renovação e preserva o período já confirmado. Reativação depende de confirmação de novo período.

Reembolsos e reversões em ambiente de testes devem atualizar o benefício associado de forma auditável. Essa transição precisa ser exercitada antes de ativar dinheiro real. Credenciais e eventos de testes nunca produzem autorização no ambiente comercial.

### 8.1. Matriz de direitos

| Condição | Resultado |
| --- | --- |
| Visitante | Prévia e perfis públicos aprovados; sem histórico completo. |
| Participante aprovado, sem vínculo ou compra | Mesma prévia, mais suas funções pessoais liberadas. |
| Vínculo ativo, inclusive adicional em leitura | Histórico próprio daquele veículo. |
| Compra vigente por placa | Histórico publicado da placa, sem dados pessoais ou documentos. |
| Compra vencida | Volta à prévia para aquela placa, salvo outro direito válido. |
| Assinatura vigente, sem vínculo validado | Capacidade comercial disponível; histórico continua bloqueado. |
| Oficina responsável pelo atendimento | Seus serviços e documentos que enviou; sem histórico completo do veículo por esse motivo. |
| Administrador | Dados necessários à operação e análise, com acessos documentais auditados. |

## 9. Ranking do piloto

Usar serviços elegíveis, não a simples marcação `completed`. Cliente e oficina se referem à mesma manutenção para evitar dupla contagem. Referências de oficinas não aprovadas ficam fora da ordenação pública.

Exibir filtros por cidade/UF e categoria. Os indicadores e suas amostras são recalculados para o recorte escolhido. Custos podem aparecer como informações descritivas de dados elegíveis, mas não influenciam a nota do piloto. Não publicar taxa de retrabalho fictícia.

### 9.1. Proposta para revisão — fórmula inicial

Versão proposta: `pilot_v1`, escala pública de 0 a 10.

- `N`: número de serviços elegíveis no recorte.
- `R`: média das estrelas convertida para 0–10 por `estrelas / 5 × 10`, somente quando houver avaliações.
- `T`: proporção de serviços entregues até a data prometida, multiplicada por 10, somente entre serviços com ambas as datas válidas.
- `V`: `10 × min(N / 20, 1)`, para limitar a contribuição do volume.
- Pesos: avaliação 40%, prazo 40%, volume 20%.
- Componentes ausentes são excluídos e os pesos presentes são normalizados; dados ausentes nunca recebem uma nota inventada.
- Com `N = 0`, mostrar “sem dados”, sem nota e sem posição.
- Com `1 ≤ N < 5`, mostrar indicadores e “amostra pequena”, fora da lista ordenada principal.
- Com `N ≥ 5`, admitir ordenação e mostrar também contagem de avaliações e de serviços com prazo mensurável.
- Se somente volume estiver disponível, mostrar os indicadores e “dados insuficientes para nota”, sem posição, mesmo com cinco serviços.
- Ordenar por nota decrescente, depois `N` decrescente e, por último, identificador estável da oficina. Arredondar só a exibição para uma casa decimal.

Exemplo: dez serviços elegíveis, média de quatro estrelas e oito de dez entregas no prazo produzem `R = 8`, `T = 8`, `V = 5` e nota `7,4`. Os pesos, o patamar de cinco e a referência de vinte são propostas, não decisões já aprovadas.

A página explica fórmula, versão, recorte e ausência de componentes. Recalcular ao publicar, contestar, corrigir ou invalidar um registro. A landing usa dados reais ou identifica explicitamente exemplos; números de demonstração não são apresentados como desempenho real.

## 10. Documentos, privacidade e auditoria

### 10.1. Upload e leitura

URLs de envio são temporárias e limitadas ao objeto autorizado. A confirmação verifica existência, tamanho e tipo do arquivo no armazenamento; declarar sucesso no navegador não basta. Reenvio não reutiliza silenciosamente um documento anteriormente aprovado.

**Proposta para revisão — limites:** PDF, JPEG, PNG e WebP, até 10 MiB por arquivo; URLs de leitura com validade de cinco minutos. A leitura exige autorização no servidor e URL assinada; não tornar o bucket público. Comprovantes enviados pela oficina só ficam disponíveis a ela e aos administradores; o cliente recebe os dados do serviço para reconhecer ou contestar. Documentos enviados pelo cliente não são compartilhados automaticamente com a oficina.

Confirmar ou ler documentos exige verificar remetente, finalidade e vínculo. Conhecer um identificador, compartilhar a mesma placa ou comprar uma consulta não autoriza acesso a arquivos de outra pessoa. Remover dados pessoais também das respostas de API, não apenas dos componentes visuais.

### 10.2. Auditoria

Registrar autor, alvo, horário, ação, versão e motivo das decisões sobre participação, administração, oficina, veículo, manutenção, disputa e benefício comercial. Guardar histórico das alterações relevantes sem expor tokens, senhas, links assinados ou conteúdo integral de documentos nos logs.

A auditoria acompanha concessões e revogações, associações de duplicidade, leitura de documentos pela administração e eventos financeiros processados. Nenhuma operação de interface apaga essa trilha.

**Proposta para revisão — preservação no piloto:** sem exclusão destrutiva automática de histórico publicado ou auditado. Pedidos de encerramento de conta e remoção de dados pessoais são registrados e tratados administrativamente, com bloqueio de acesso quando aplicável. A política definitiva de retenção e anonimização é requisito de preparação comercial.

## 11. Experiências e notificações necessárias

| Área | Experiências necessárias |
| --- | --- |
| Pública | Landing coerente com o piloto, prévia por placa, ranking, perfil aprovado, cadastro e entrada. |
| Conta | Perfil, situação do pedido, pendências, recuperação de acesso, saída e capacidades de cliente/oficina. |
| Garagem | Lista, cadastro, checklist, situação documental, assinatura, escolha da vaga gratuita, histórico e manutenção. |
| Oficina | Solicitar/reivindicar perfil, acompanhar aprovação, registrar serviço, anexar comprovante, convidar cliente e acompanhar confirmação/disputa. |
| Cliente | Ver atendimentos aguardando reconhecimento, confirmar, contestar e avaliar. |
| Consulta paga | Explicação da prévia, checkout de testes, pedido pendente, histórico liberado, prazo e vencimento. |
| Administração | Filas separadas, detalhe completo com evidências, decisões, solicitações de correção, contestações e auditoria. |

Notificar quando houver aprovação/rejeição, documento adicional solicitado, serviço aguardando reconhecimento, contestação ou benefício alterado. **Proposta para revisão:** central de pendências no app e e-mail transacional para convites e recuperação; evitar SMS e WhatsApp no piloto. Falha de envio não aprova nem confirma nada, e permite reenvio controlado.

Erros de API não podem aparecer como listas vazias ou carregamento infinito. Expiração de sessão solicita nova entrada. Uma URL direta não contorna perfil, participação, vínculo, assinatura ou compra. A mesma autorização vale para frontend e chamadas diretas à API.

## 12. Arquitetura e impacto no código existente

Preservar FastAPI, SQLAlchemy assíncrono, PostgreSQL, Alembic, React/TypeScript e armazenamento privado R2. Redis/Celery pode apoiar notificações e tarefas, mas a concessão de acesso precisa ser verificável no banco e não depender apenas de estado no navegador ou na fila.

O domínio deve distinguir:

| Unidade | Responsabilidade |
| --- | --- |
| Identidade e participação | Autenticação, capacidades combináveis, aprovação e administração. |
| Oficinas e representação | Identidade por CNPJ, reivindicação, aprovação e responsáveis. |
| Veículo e vínculo | Identidade por placa, evidências e autorização pessoal. |
| Garagem e benefícios | Vaga gratuita, limite de cinco e restrição dos adicionais. |
| Manutenção e versões | Serviço único, origem, comprovantes, reconhecimento e publicação. |
| Moderação e disputas | Decisões documentais, correções, contestação e auditoria. |
| Compras e assinatura | Pedido, eventos do provedor, validade e direitos comerciais. |
| Consulta e ranking | Projeções dos dados elegíveis, com exposição mínima. |

Uma política compartilhada define publicação e acesso. Consulta pública, consulta comprada e ranking devem usar essa política, evitando três interpretações diferentes de registro válido.

### 12.1. Lacunas existentes que esta spec exige resolver

- `User.profile_type` exclusivo não representa cliente e responsável simultaneamente; migrar sem elevar permissões de contas existentes.
- Unificar regras de criação de veículos das rotas `/vehicles` e `/garage/vehicles`.
- Separar permissão para rascunho próprio de permissão para ler histórico anterior e documentos privados.
- Substituir a elegibilidade baseada apenas em `MaintenanceStatus.COMPLETED` por aprovação, reconhecimento e ausência de disputa.
- Acrescentar origem oficina, convites, versões, avaliações, moderação de manutenção e contestação.
- Completar R2: inspeção do upload e leitura privada autorizada.
- Corrigir caminhos e payloads de manutenção e campos obrigatórios do cadastro de oficina no frontend.
- Conectar upload, envio para análise, timeline e perfil de oficina às telas corretas.
- Corrigir navegação, configurar CORS e tratar sessão, perfis, falhas e estados vazios.
- Criar compras, assinatura e webhooks, hoje ausentes no módulo `payments`.
- Revisar migrações reais, inclusive representação de enums e valores padrão, sem depender apenas de testes que recriam tabelas em SQLite.

Esta seção é um mapa de impacto, não um plano de execução. Os planos seguintes devem decompor os subsistemas em entregas revisáveis, com contratos definidos entre eles.

## 13. Critérios de aceite do piloto

| ID | Cenário observável |
| --- | --- |
| A01 | Cadastro público cria participante pendente; chamada direta à API não libera operação antes de aprovação. |
| A02 | Uma conta aprovada usa garagem e solicita oficina, cuja análise permanece independente. |
| A03 | Dois administradores podem operar; cada decisão tem autor e conflitos de versão não são sobrescritos. |
| A04 | Nenhuma rota permite obter uma segunda vaga gratuita ou ultrapassar cinco vagas liberadas. |
| A05 | Declarar placa ou usar convite não revela histórico anterior nem documentos de terceiros. |
| A06 | Primeiro veículo validado acessa histórico próprio; adicional validado respeita a assinatura. |
| A07 | Cliente e oficina conseguem enviar manutenção com comprovante; arquivo ausente ou inválido não satisfaz a exigência. |
| A08 | Origem cliente só publica após análise; origem oficina requer também confirmação do cliente da mesma versão. |
| A09 | Serviço para cliente sem conta permanece pendente até identidade, participação, vínculo e reconhecimento serem resolvidos. |
| A10 | Associação das duas origens produz uma manutenção publicada e uma contribuição nas métricas. |
| A11 | Contestação retira serviço e avaliação da publicação/ranking; correção exige os novos atos aplicáveis. |
| A12 | Mudança relevante invalida as autorizações da versão anterior e preserva auditoria. |
| A13 | Prévia contém somente agregados elegíveis; comprador não recebe dados pessoais nem arquivos brutos. |
| A14 | Pagamento de testes confirmado libera uma placa por exatamente 30 dias; retorno do checkout sozinho não libera. |
| A15 | Durante os 30 dias, novos registros aprovados aparecem; no vencimento, acesso de terceiros é negado no servidor. |
| A16 | Webhook repetido ou fora de ordem não duplica benefícios; assinatura respeita período confirmado, limite e cancelamento. |
| A17 | Sem renovação, adicionais preservam leitura autorizada e bloqueiam novos lançamentos diretos, mantendo a vaga gratuita. |
| A18 | Avaliação aceita apenas 1–5, uma por serviço reconhecido; autorrepresentação da oficina impede avaliar. |
| A19 | Ranking é reproduzível por sua versão, recorte e amostras; ausência de dados não produz notas fictícias. |
| A20 | Todas as jornadas principais funcionam no frontend conectado ao backend, inclusive erros de autorização e sessão. |

## 14. Verificação e operação do piloto

Os testes precisam incluir autorização por ator, transições inválidas, envio duplicado, concorrência de aprovação, expiração no instante correto e indisponibilidade de armazenamento/provedor. A suite existente não substitui esses cenários novos.

Verificar migração de base vazia e de base anterior com dados em PostgreSQL, além dos testes rápidos de domínio. Conferir compatibilidade dos contratos frontend/backend e realizar testes de jornada de cadastro, validação, manutenção nas duas origens, contestação, compra e fim de assinatura.

Para disponibilizar o piloto: implantação de testes com HTTPS, bucket privado, segredos externos ao código, administrador inicial provisionado, restauração de backup exercitada e instruções para revisão das filas. Proteger cadastro, login, consulta por placa e geração de convites contra repetição abusiva.

Falhas de teste, build ou migração bloqueiam declarar a versão pronta. O diagnóstico anterior validou somente sintaxe Python; as suites e o build ainda precisam ser executados em ambiente com dependências disponíveis.

## 15. Aprendizado do piloto e passagem ao MVP comercial

Medir cadastro até aprovação, cadastro de veículo até vínculo ativo, manutenção enviada até publicada, convites até confirmação, causas de rejeição, tempo e esforço da moderação, frequência de duplicidades/contestações, completude de prazo/avaliação, compras de testes e expiração de acessos.

Registrar devolutivas de clientes, oficinas e administradores. **Proposta para revisão:** exigir ao menos uma jornada acompanhada de cada origem, um cliente convidado sem conta anterior, uma contestação, uma correção, uma compra com vencimento e um cancelamento de assinatura. Esse mínimo comprova cobertura operacional, não valida demanda comercial nem significância do ranking.

Para avançar ao MVP comercial:

- Critérios A01–A20 demonstrados, com testes e revisão das permissões.
- Operação administrativa consegue acompanhar as filas e explicar as decisões.
- Sem falhas conhecidas que exponham dados, publiquem serviços inelegíveis ou concedam benefícios sem confirmação.
- Escolha e validação do provedor em produção, preços, suporte, cancelamento/reembolso, recuperação de incidentes e política de retenção/privacidade definidos para operação real.
- Separação comprovada entre dados e credenciais de testes e de produção.
- Revisão da fórmula após observar quantidade, diversidade e completude dos registros.

O primeiro MVP comercial mantém o núcleo validado e ativa a operação financeira real. Ranking por preço/retrabalho, OCR e marketplace exigem decisões próprias posteriores; não são condição automática para ligar a cobrança.

## 16. Registro das decisões complementares aceitas na revisão

| Ponto | Proposta presente no desenho |
| --- | --- |
| Participação | Estados pendente/aprovado/rejeitado/suspenso; suspensão bloqueia acessos autenticados. |
| Administradores | Proteger o último ativo e impedir aprovação do próprio pedido. |
| Representação | Documentos do responsável; oficina não verificada sem posição no ranking. |
| Garagem pendente | Permitir preparar rascunho próprio; exigir vínculo ativo para enviá-lo à moderação. |
| Fim da assinatura | Benefício até fim do período confirmado; primeiro veículo vigente como seleção padrão do gratuito. |
| Restrição de adicionais | Não impedir contestação, regularização documental ou resposta a serviço da oficina. |
| Comprovantes | Nota fiscal, recibo ou ordem de serviço identificável; revisão pode exigir complemento. |
| Convite | Link opaco, único, revogável e válido por sete dias; vínculo validado continua obrigatório. |
| Duplicidade | Sugerir associação; nunca mesclar automaticamente só por placa/data. |
| Edição relevante | Retirar publicação até nova aprovação e reconhecimento aplicável. |
| Disputa | Pode ser aberta após confirmação e reaberta com nova justificativa auditada. |
| Avaliação | Opcional; ausência não afeta volume/prazo e nunca significa cinco estrelas. |
| Nova compra | Sem duplicar checkout durante acesso vigente; novo período depois do vencimento. |
| Ranking | Fórmula, pesos 40/40/20, referência de vinte, mínimo de cinco e tratamento de componentes ausentes. |
| Arquivos | Máximo 10 MiB; leitura assinada por cinco minutos; arquivos restritos ao remetente e administração. |
| Notificações | Pendências no app; e-mail para convites e recuperação; sem SMS/WhatsApp no piloto. |
| Preservação | Remoção de dados pessoais tratada administrativamente no piloto, sem exclusão automática destrutiva. |
| Saída do piloto | Cobertura acompanhada dos casos operacionais da seção 15, sem meta comercial inventada. |

Aceite registrado em 21/10/2026. Os planos técnicos ficam em `../plans/2026-10-21-piloto-00-coordenacao.md`; mudanças posteriores de comportamento devem atualizar esta spec e os planos afetados.
