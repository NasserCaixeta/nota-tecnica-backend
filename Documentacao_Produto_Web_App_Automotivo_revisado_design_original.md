# Documentação de Produto — Web App Automotivo de Ranking de Oficinas e Histórico Veicular

## 0. Visão Geral do Produto

O produto será um Web App automotivo com duas verticais principais:

- **Ranking objetivo e qualificado de oficinas**, baseado predominantemente em dados concretos de preço, prazo, retrabalho e consistência operacional.

- **Garagem digital do cliente**, com guarda, gestão e histórico de manutenções vinculado à **placa do veículo**, e não apenas ao CPF do proprietário atual.

O objetivo central é criar uma camada de confiança no mercado automotivo, reduzindo assimetrias de informação entre donos de veículos, oficinas mecânicas, centros de estética automotiva e potenciais compradores de veículos usados.

# 1. Arquitetura da Informação e Sitemap

## 1.1. Princípios de arquitetura

O sistema deve ser desenhado com quatro princípios estruturantes:

### 1.1.1. Histórico centrado na placa

A entidade mais importante do sistema não é o usuário, nem a oficina, mas o **veículo identificado pela placa**.

Isso significa que:

- o histórico acompanha o carro;

- o usuário atual pode ter acesso ao histórico se comprovar legitimidade ou pagar pelo acesso permitido;

- a venda do veículo não apaga o histórico;

- o CPF serve para vincular pessoas físicas;

- o CNPJ serve para vincular oficinas e também pessoas jurídicas proprietárias ou responsáveis por veículos;

- o vínculo veículo-titular deve aceitar CPF ou CNPJ, mantendo a placa como eixo histórico principal;

- a placa serve como eixo histórico principal.

### 1.1.2. Ranking baseado em dados verificáveis

A nota principal da oficina deve ser uma nota objetiva, calculada a partir de:

- preço de mão de obra;

- preço de peças;

- tempo de execução;

- cumprimento de prazo;

- taxa de retrabalho;

- volume de serviços registrados;

- consistência por categoria de serviço.

A avaliação subjetiva do cliente entra como fator complementar e minoritário.

### 1.1.3. Paywall com fricção reduzida

Os paywalls devem aparecer em momentos de valor percebido alto, nunca cedo demais.

O usuário deve entender claramente:

- o que está desbloqueando;

- por que aquilo tem valor;

- o que verá antes de pagar;

- se o pagamento é único, recorrente ou variável;

- se há dados suficientes para justificar a cobrança.

### 1.1.4. Dois mundos com uma base comum

O app terá duas experiências principais:

- **Cliente / Dono de veículo / Comprador de usado**;

- **Oficina / Prestador de serviço automotivo**.

Ambas compartilham a base de dados de manutenção, mas com permissões, telas e objetivos diferentes.

# 1.2. Sitemap geral do Web App

## 1.2.1. Área pública

### Página inicial

Objetivo: explicar rapidamente o valor do produto para clientes e oficinas.

Seções recomendadas:

- Hero principal:

- “Descubra o histórico real do veículo e encontre oficinas ranqueadas por dados, não só por estrelas.”

- CTA primário:

- “Consultar veículo”

- CTA secundário:

- “Cadastrar minha oficina”

- Explicação em três passos:

- Cadastre ou consulte uma placa;

- Veja histórico, manutenções e oficinas;

- Tome decisões com mais segurança.

- Destaque de confiança:

- Histórico vinculado à placa;

- Oficinas vinculadas a CNPJ;

- Ranking por preço, prazo e retrabalho.

- Bloco para oficinas:

- “Sua oficina pode ser ranqueada por performance real.”

- Bloco para compradores:

- “Antes de comprar um usado, veja o que já foi feito no carro.”

### Página de consulta por placa

Função: permitir que qualquer usuário digite uma placa e veja uma prévia limitada.

Campos:

- Placa do veículo;

- Estado opcional;

- Botão “Consultar histórico”.

Resultado pré-paywall:

- Veículo encontrado ou não encontrado;

- Quantidade de eventos de manutenção disponíveis;

- Período coberto pelo histórico;

- Categorias de manutenção existentes;

- Indicação de oficinas registradas;

- Selo de qualidade dos dados;

- CTA “Desbloquear histórico completo”.

Importante: antes do pagamento, não mostrar detalhes sensíveis, notas fiscais completas, documentos ou dados pessoais.

### Página de ranking público de oficinas

Função: permitir busca e comparação de oficinas.

Filtros:

- Cidade / região;

- Tipo de serviço;

- Marca do veículo;

- Especialidade;

- Faixa de preço;

- Nota objetiva;

- Menor taxa de retrabalho;

- Melhor prazo médio;

- Melhor custo-benefício;

- Oficinas verificadas.

Cards de oficinas:

- Nome fantasia;

- CNPJ verificado;

- Cidade;

- Especialidades;

- Nota objetiva;

- Nota de atendimento;

- Preço relativo;

- Tempo médio;

- Taxa de retrabalho;

- Quantidade de serviços registrados;

- CTA “Ver perfil”.

### Página pública de perfil da oficina

Função: apresentar a reputação objetiva da oficina.

Conteúdo:

- Nome da oficina;

- CNPJ;

- Status de verificação;

- Endereço;

- Especialidades;

- Ranking geral;

- Ranking por categoria de serviço;

- Indicadores:

- competitividade de preço;

- prazo médio;

- retrabalho;

- atendimento;

- volume de serviços;

- Serviços mais realizados;

- Avaliações de clientes;

- CTA “Solicitar orçamento”;

- CTA “Registrar manutenção feita aqui”.

### Login / Cadastro

Perfis possíveis:

- Cliente;

- Oficina;

- Admin interno.

Cadastro de cliente:

- Nome;

- CPF;

- e-mail;

- telefone;

- senha ou login social;

- aceite de termos;

- aceite de política de privacidade.

Cadastro de oficina:

- CNPJ;

- razão social;

- nome fantasia;

- e-mail;

- telefone;

- endereço;

- responsável;

- CPF do responsável;

- documentos de validação;

- aceite de termos;

- aceite de regras de ranqueamento.

# 1.3. Sitemap da visão do cliente

## Dashboard do cliente

Página inicial após login.

Elementos:

- Resumo da garagem;

- Lista de veículos cadastrados;

- Status de validação de propriedade;

- Alertas de manutenção;

- Histórico recente;

- Recomendações de oficinas;

- CTA “Adicionar veículo”;

- CTA “Consultar veículo usado”;

- CTA “Registrar manutenção”.

## Minha Garagem

Lista de veículos vinculados ao usuário, seja por CPF próprio, autorização, vínculo familiar ou representação de CNPJ.

Para cada veículo:

- Foto ou ícone;

- Placa;

- Marca/modelo/ano;

- Status de validação;

- Última manutenção;

- Próxima manutenção prevista;

- Indicador de histórico disponível;

- CTA “Ver dashboard”.

Estados:

- Nenhum veículo cadastrado;

- Um veículo gratuito cadastrado;

- Tentativa de segundo veículo com paywall;

- Veículo pendente de validação;

- Veículo rejeitado;

- Veículo validado.

## Adicionar veículo

Fluxo dividido em etapas:

- Inserir placa;

- Confirmar dados básicos do veículo;

- Enviar CRLV;

- Validar se o titular do documento é compatível com o CPF do usuário ou com um CNPJ que ele esteja autorizado a representar;

- Se o titular for CNPJ, validar o vínculo do usuário com a empresa antes de liberar gestão completa;

- Se não bater, solicitar documentos adicionais;

- Confirmar vínculo;

- Criar dashboard do veículo;

- Exibir paywall se for segundo veículo ou posterior.

## Dashboard do veículo

Página central da experiência do cliente.

Conteúdo:

- Placa;

- Marca/modelo/ano;

- Status de posse;

- Linha do tempo de manutenções;

- Custos acumulados;

- Separação mão de obra x peças;

- Oficinas utilizadas;

- Alertas;

- Próximos serviços recomendados;

- Documentos anexados;

- CTA “Adicionar manutenção”;

- CTA “Compartilhar histórico”;

- CTA “Gerar relatório para venda”.

## Histórico de manutenção

Visualização completa e filtrável.

Filtros:

- Data;

- Oficina;

- Tipo de serviço;

- Sistema do veículo;

- Valor;

- Peça;

- Garantia;

- Retrabalho;

- Avaliação.

Cada item deve mostrar:

- Data;

- Oficina;

- Serviço;

- Valor de mão de obra;

- Valor das peças;

- Valor total;

- Quilometragem;

- Peças trocadas;

- Comprovantes;

- Avaliação;

- Possível retrabalho associado.

## Adicionar manutenção

Fluxo de input manual ou vinculado à oficina.

Campos obrigatórios:

- Placa;

- Quilometragem;

- Data;

- Tipo de serviço;

- Oficina;

- CNPJ da oficina;

- Valor da mão de obra;

- Valor das peças;

- Descrição do serviço;

- Peças substituídas;

- Garantia;

- Comprovante opcional ou recomendado.

Campos opcionais:

- Fotos;

- Nota fiscal;

- Ordem de serviço;

- Observações;

- Próxima revisão recomendada.

Ao final:

- Tela de confirmação;

- Avaliação subjetiva;

- Pergunta sobre atendimento pré-venda;

- Pergunta sobre atendimento pós-venda;

- Pergunta sobre clareza no orçamento;

- Pergunta sobre cumprimento do prazo informado.

## Consultar carro usado

Fluxo para usuário que pretende comprar um veículo.

Etapas:

- Informar placa;

- Ver prévia do histórico;

- Ver quantidade de registros;

- Ver período coberto;

- Ver score de confiabilidade do histórico;

- Paywall;

- Pagamento;

- Liberação do relatório completo;

- Possibilidade de salvar consulta.

## Pagamentos

Área para:

- Adicionar segundo veículo;

- Comprar histórico completo;

- Ver recibos;

- Gerenciar assinatura, se houver;

- Ver consultas compradas;

- Renovar acesso a relatórios.

## Conta e privacidade

Itens:

- Dados pessoais;

- CPF;

- E-mail;

- Telefone;

- Segurança;

- Consentimentos;

- Exclusão de conta;

- Permissões de compartilhamento de histórico.

# 1.4. Sitemap da visão da oficina

## Dashboard da oficina

Página inicial da oficina.

Elementos:

- Status de verificação do CNPJ;

- Ranking geral;

- Ranking por categoria;

- Serviços registrados no mês;

- Ticket médio;

- Tempo médio de finalização;

- Taxa de retrabalho;

- Avaliação de atendimento;

- Solicitações de clientes;

- Alertas de dados incompletos;

- CTA “Registrar serviço”.

## Perfil da oficina

Página editável pela oficina.

Campos:

- Nome fantasia;

- Razão social;

- CNPJ;

- Endereço;

- Fotos;

- Horário de funcionamento;

- Especialidades;

- Marcas atendidas;

- Serviços prestados;

- Certificações;

- Garantias oferecidas;

- Política de peças;

- Contatos;

- Link de WhatsApp;

- Website.

## Serviços

Lista dos serviços realizados.

Cada serviço:

- Placa;

- Data;

- Cliente;

- Tipo de serviço;

- Valor da mão de obra;

- Valor das peças;

- Status;

- Prazo prometido;

- Prazo real;

- Avaliação;

- Possível retrabalho.

## Registrar serviço

Fluxo para oficina cadastrar manutenção.

Campos obrigatórios:

- Placa;

- CPF ou CNPJ do cliente/titular, quando aplicável;

- Quilometragem;

- Tipo de serviço;

- Sistema do veículo;

- Descrição;

- Data de entrada;

- Data de entrega prevista;

- Data de entrega efetiva;

- Valor da mão de obra;

- Valor das peças;

- Lista de peças;

- Garantia;

- Anexos.

## Ranking e performance

Tela analítica.

Métricas:

- Nota geral;

- Nota por serviço;

- Posição no ranking local;

- Comparativo com oficinas similares;

- Preço médio vs mercado;

- Tempo médio vs mercado;

- Retrabalho vs mercado;

- Atendimento vs mercado;

- Volume de dados;

- Recomendações de melhoria.

## Solicitações de orçamento

Área comercial.

Estados:

- Nova solicitação;

- Em análise;

- Orçamento enviado;

- Aceito;

- Recusado;

- Convertido em serviço.

## Validação de CNPJ

Fluxo obrigatório.

Etapas:

- Informar CNPJ;

- Confirmar dados cadastrais;

- Enviar documentos, se necessário;

- Validar responsável;

- Aceitar termos;

- Status de aprovação.

## Conta da oficina

Configurações:

- Usuários da equipe;

- Permissões;

- Dados financeiros;

- Planos;

- Integrações;

- Notificações;

- Privacidade.

# 1.5. Área administrativa

Mesmo que não seja exposta ao público, o sistema precisa de uma camada admin.

Páginas:

- Painel geral;

- Oficinas pendentes de validação;

- Veículos pendentes de validação;

- CRLVs pendentes;

- Documentos adicionais;

- Moderação de avaliações;

- Auditoria de retrabalho;

- Denúncias;

- Pagamentos;

- Relatórios;

- Configuração do algoritmo de ranking;

- Tabelas de referência de serviços;

- Categorias de manutenção;

- Gestão de usuários;

- Logs de acesso ao histórico.

# 2. User Journeys

## 2.1. Jornada 1 — Cliente cadastrando um veículo que não está no nome dele

### Contexto

O cliente quer adicionar um veículo à sua garagem, mas o CRLV está em nome de outra pessoa, por exemplo, mãe, pai, cônjuge, empresa familiar ou antigo proprietário.

Objetivo UX: permitir o cadastro sem bloquear prematuramente, mas exigir comprovação adicional antes de liberar funcionalidades sensíveis.

## Etapa 1 — Entrada no app

Tela: Home ou Dashboard do Cliente.

CTA principal:

- “Adicionar veículo à minha garagem”.

Microcopy recomendada:

Cadastre seu veículo para organizar manutenções, guardar comprovantes e acompanhar o histórico vinculado à placa.

## Etapa 2 — Verificação do limite gratuito

O sistema verifica quantos veículos já existem na garagem do usuário.

### Caso seja o primeiro veículo

Prossegue gratuitamente.

Mensagem:

Seu primeiro veículo é gratuito.

### Caso seja o segundo veículo ou posterior

Exibir paywall antes do cadastro definitivo, mas depois de explicar valor.

Estrutura do paywall:

- Título:

- “Adicione mais veículos à sua garagem”

- Benefícios:

- histórico individual por placa;

- alertas de manutenção;

- armazenamento de comprovantes;

- relatório para venda;

- acesso organizado aos custos.

- Preço;

- CTA:

- “Continuar com este veículo”

- CTA secundário:

- “Agora não”.

Boa prática: permitir que o usuário digite a placa e veja uma prévia antes de pagar, mas bloquear a conclusão do vínculo.

## Etapa 3 — Inserção da placa

Campos:

- Placa do veículo.

Botão:

- “Buscar veículo”.

Validações:

- formato de placa brasileira antiga ou Mercosul;

- normalização de caracteres;

- remoção automática de espaços e hífen;

- feedback imediato se o formato for inválido.

Tela de carregamento:

Buscando dados básicos do veículo…

## Etapa 4 — Confirmação dos dados básicos

Tela mostra:

- Placa;

- Marca;

- Modelo;

- Ano;

- Cor, se disponível;

- Renavam parcial mascarado, se aplicável;

- Mensagem de confirmação.

Pergunta:

Este é o veículo que você deseja adicionar?

Botões:

- “Sim, continuar”

- “Não, corrigir placa”

## Etapa 5 — Upload do CRLV

Tela: “Comprove o vínculo com o veículo”.

Elementos:

- Upload de arquivo PDF, imagem ou foto;

- Orientações visuais:

- documento legível;

- sem cortes;

- dados do proprietário visíveis;

- placa visível;

- Exemplo ilustrativo;

- Botão:

- “Enviar CRLV”.

Microcopy:

Usamos o CRLV para confirmar que você tem autorização para gerenciar este veículo. Seus documentos não serão exibidos publicamente.

## Etapa 6 — Leitura e comparação dos dados

O sistema tenta identificar:

- nome do proprietário no CRLV;

- CPF ou CNPJ do proprietário, se disponível;

- placa;

- exercício;

- dados do veículo.

Comparação:

- CPF do usuário ou CNPJ representado vs CPF/CNPJ do proprietário no CRLV;

- nome do usuário, razão social ou representante autorizado vs titular do documento;

- placa informada vs placa no documento.

### Caso esteja no nome do usuário ou de CNPJ representado por ele

Status:

- Veículo validado.

Próxima tela:

- “Veículo adicionado com sucesso”.

### Caso não esteja no nome do usuário nem de CNPJ representado por ele

Entrar no fluxo de justificativa.

## Etapa 7 — Documento não está no nome do usuário ou do CNPJ representado

Tela: “O documento está em nome de outra pessoa ou empresa”.

Mensagem:

Identificamos que o CRLV não está no seu nome ou no CNPJ que você representa. Para proteger o histórico do veículo, precisamos entender sua relação com o proprietário ou responsável legal.

Campo obrigatório:

- “Qual é sua relação com o proprietário ou responsável legal?”

Opções:

- Mãe;

- Pai;

- Cônjuge;

- Filho(a);

- Sócio(a);

- Empresa da qual faço parte ou represento;

- Veículo de frota;

- Comprei recentemente;

- Outro.

## Etapa 8 — Solicitação de documentos adicionais

A interface deve variar conforme a relação informada.

### Exemplo: veículo no nome da mãe

Solicitar:

- RG ou CNH do usuário;

- documento que comprove filiação, se o RG/CNH não mostrar;

- declaração simples de autorização, se necessário.

Microcopy:

Como o veículo está no nome de sua mãe, envie um documento que comprove a filiação ou uma autorização da proprietária.

### Exemplo: veículo em nome de empresa

Solicitar:

- contrato social;

- autorização da empresa;

- documento do representante;

- comprovação de vínculo.

### Exemplo: veículo recém-comprado

Solicitar:

- recibo de compra e venda;

- ATPV-e, quando disponível;

- contrato de compra;

- comprovante de pagamento, opcional;

- CRLV atual.

## Etapa 9 — Status de análise

Após o envio:

Tela de confirmação:

Recebemos seus documentos. O veículo ficará com status “em análise” até a validação.

Status funcional:

- O usuário pode criar manutenções privadas;

- O usuário não pode compartilhar relatório oficial;

- O usuário não pode alterar dados sensíveis do veículo;

- O usuário não pode reivindicar propriedade plena;

- O histórico fica marcado como pendente de validação.

## Etapa 10 — Aprovação

Notificação:

Veículo validado. Agora você pode gerenciar o histórico completo desta placa na sua garagem.

CTA:

- “Ir para o dashboard do veículo”.

## Etapa 11 — Reprovação ou pendência

Mensagem clara:

Não conseguimos validar o vínculo com os documentos enviados.

Ações:

- “Enviar novo documento”;

- “Falar com suporte”;

- “Manter veículo como acompanhamento privado”.

UX importante: não tratar reprovação como acusação. A linguagem deve ser neutra.

# 2.2. Jornada 2 — Cliente inserindo histórico de manutenção e avaliando o serviço

### Contexto

O cliente fez uma manutenção e deseja registrar no histórico do veículo. Esse registro alimentará o dashboard do veículo e poderá impactar métricas da oficina.

## Etapa 1 — Acesso ao dashboard do veículo

O usuário entra na garagem e seleciona um veículo.

CTA principal:

- “Adicionar manutenção”.

CTA secundário:

- “Escanear nota ou ordem de serviço”.

## Etapa 2 — Escolha do tipo de entrada

Tela: “Como você quer adicionar a manutenção?”

Opções:

- “Preencher manualmente”;

- “Usar nota fiscal ou ordem de serviço”;

- “Selecionar serviço registrado pela oficina”.

A terceira opção aparece se houver manutenção pendente de confirmação criada por uma oficina.

## Etapa 3 — Dados básicos

Campos:

- Data do serviço;

- Quilometragem;

- Categoria:

- mecânica;

- elétrica;

- funilaria;

- pintura;

- estética;

- pneus;

- revisão;

- diagnóstico;

- outro.

- Sistema do veículo:

- motor;

- câmbio;

- freios;

- suspensão;

- ar-condicionado;

- direção;

- elétrica;

- acabamento;

- carroceria;

- pintura;

- estética;

- pneus;

- outros.

- Descrição breve.

Botão:

- “Continuar”.

## Etapa 4 — Oficina

Campos:

- Nome da oficina;

- CNPJ da oficina;

- Endereço, se necessário.

UX recomendada:

- Campo com autocomplete por nome ou CNPJ;

- Se oficina já existir, o usuário seleciona;

- Se não existir, o usuário pode cadastrar uma oficina via crowdsourcing.

### Cadastro crowdsourced de oficina

Campos mínimos:

- Nome fantasia;

- CNPJ;

- Cidade;

- Telefone opcional;

- Endereço opcional;

- Foto opcional.

Mensagem:

A oficina será vinculada ao CNPJ informado. Ela poderá reivindicar este perfil posteriormente.

## Etapa 5 — Valores obrigatoriamente segregados

Tela: “Valores do serviço”.

Campos obrigatórios:

- Valor da mão de obra;

- Valor das peças.

Campo calculado:

- Valor total.

Campos opcionais:

- Desconto;

- Forma de pagamento;

- Número da nota fiscal;

- Garantia em dias ou meses.

Microcopy essencial:

Separe mão de obra e peças. Isso ajuda a calcular preços mais justos e rankings mais precisos.

Validação:

- Não permitir apenas “valor total”;

- Se uma das partes for zero, exigir justificativa:

- “Serviço sem troca de peças”;

- “Peça fornecida pelo cliente”;

- “Garantia sem custo”;

- “Cortesia”;

- “Outro”.

## Etapa 6 — Peças e serviços

Lista dinâmica de itens.

Para cada peça:

- Nome da peça;

- Marca;

- Código, se disponível;

- Nova, usada ou recondicionada;

- Quantidade;

- Valor unitário;

- Garantia;

- Observações.

Para cada serviço:

- Tipo de serviço;

- Sistema afetado;

- Descrição;

- Valor atribuído, se houver rateio;

- Tempo estimado;

- Tempo real, se conhecido.

## Etapa 7 — Prazo

Campos:

- Data de entrada;

- Data prometida;

- Data de entrega;

- Entregue no prazo?

- Houve atraso?

- Motivo do atraso, se informado.

Esses dados alimentam a métrica objetiva de tempo.

## Etapa 8 — Anexos

Opções:

- Nota fiscal;

- Ordem de serviço;

- Foto antes;

- Foto depois;

- Comprovante de pagamento;

- Laudo;

- Garantia.

UX:

- Drag and drop no desktop;

- Upload por câmera no mobile;

- Indicação de segurança dos documentos.

## Etapa 9 — Revisão antes de salvar

Tela resumo:

- Veículo;

- Placa;

- Data;

- Oficina;

- CNPJ;

- Categoria;

- Mão de obra;

- Peças;

- Total;

- Prazo;

- Peças substituídas;

- Anexos.

Botões:

- “Editar”

- “Salvar manutenção”

## Etapa 10 — Confirmação e avaliação

Após salvar:

Tela: “Manutenção registrada com sucesso”.

Em seguida, avaliação subjetiva.

Campos:

- Atendimento pré-venda: 1 a 5;

- Clareza do orçamento: 1 a 5;

- Comunicação durante o serviço: 1 a 5;

- Atendimento pós-venda: 1 a 5;

- Recomendaria a oficina? Sim/Não;

- Comentário opcional.

Mensagem:

Sua avaliação de atendimento ajuda outros motoristas, mas a nota principal da oficina também considera preço, prazo e retrabalho.

## Etapa 11 — Pergunta de retrabalho

Pergunta após alguns dias ou ao registrar novo serviço semelhante:

Esse serviço resolveu o problema?

Opções:

- Sim;

- Parcialmente;

- Não;

- Ainda não sei.

Se o usuário responder “Não” ou “Parcialmente”, o sistema pode abrir fluxo de possível retrabalho.

Campos:

- O problema voltou?

- Quantos dias depois?

- A oficina refez o serviço?

- Houve novo custo?

- Foi a mesma peça ou sistema?

- Foi garantia?

Essa etapa é essencial para evitar que o sistema classifique qualquer retorno como retrabalho automaticamente.

# 2.3. Jornada 3 — Usuário consultando histórico de carro usado antes da compra

### Contexto

Um usuário está avaliando comprar um veículo usado e quer consultar o histórico atrelado à placa.

Objetivo UX: entregar valor antes do paywall, mas proteger o histórico completo.

## Etapa 1 — Entrada

Caminhos possíveis:

- Home pública;

- CTA “Consultar veículo usado”;

- Dashboard do cliente;

- Link compartilhado por vendedor;

- Perfil público de veículo, se existir.

Tela:

- Campo “Digite a placa”;

- Botão “Consultar histórico”.

## Etapa 2 — Resultado preliminar

O sistema busca a placa.

### Caso não haja dados

Mensagem:

Ainda não encontramos histórico de manutenção para esta placa.

Ações:

- “Criar alerta se aparecer histórico”

- “Cadastrar este veículo”

- “Consultar outro veículo”

Não cobrar se não houver histórico.

### Caso haja dados

Exibir prévia.

Prévia recomendada:

- Marca/modelo/ano;

- Quantidade de registros de manutenção;

- Período coberto:

- “Histórico de 2021 a 2026”

- Quilometragens registradas;

- Categorias encontradas:

- revisão;

- freios;

- suspensão;

- motor;

- funilaria;

- estética;

- Número de oficinas envolvidas;

- Existência de eventos críticos sem revelar detalhes:

- “Há registros de serviços recorrentes no mesmo sistema”

- “Há trocas relevantes de peças”

- “Há registros de manutenção preventiva”

- Score de completude do histórico:

- baixo;

- médio;

- alto.

## Etapa 3 — Tela de valor antes do paywall

A tela deve responder à pergunta: “Por que eu pagaria por isso?”

Blocos:

- “O que você verá no relatório completo”

- linha do tempo de manutenções;

- oficinas utilizadas;

- valores pagos;

- separação entre peças e mão de obra;

- recorrência de problemas;

- sinais de retrabalho;

- histórico de quilometragem informada;

- anexos disponíveis, quando liberados;

- resumo para decisão de compra.

- “Por que isso importa”

- ajuda a negociar preço;

- reduz risco de compra;

- revela padrão de manutenção;

- identifica serviços repetidos;

- mostra se o carro teve cuidado preventivo.

## Etapa 4 — Paywall

Título:

Desbloqueie o histórico completo desta placa

Preço pode ser:

### Modelo fixo

- “Relatório completo por R$ X”

### Modelo variável por anos de histórico

Exemplo:

- Até 2 anos de histórico: R$ X;

- 3 a 5 anos: R$ Y;

- Mais de 5 anos: R$ Z.

UX recomendada:

Mostrar a justificativa:

Este veículo possui 5 anos de histórico e 18 registros de manutenção disponíveis.

Botões:

- “Desbloquear relatório”

- “Ver exemplo de relatório”

- “Consultar outra placa”

Garantia de clareza:

- Informar que o pagamento libera o histórico daquela placa;

- Informar período de acesso;

- Informar se o usuário poderá baixar PDF;

- Informar se atualizações futuras estão incluídas ou não.

## Etapa 5 — Checkout simplificado

Campos:

- E-mail;

- CPF, se necessário para nota;

- Forma de pagamento;

- Cupom, se houver.

Opções:

- Pix;

- cartão;

- carteira digital.

Evitar criação obrigatória de conta antes do pagamento. Melhor fluxo:

- usuário informa e-mail;

- paga;

- acessa relatório;

- depois é convidado a criar conta para salvar o relatório.

## Etapa 6 — Relatório liberado

Tela pós-pagamento:

- “Histórico desbloqueado”

- CTA:

- “Ver relatório”

- CTA secundário:

- “Baixar PDF”

- CTA terciário:

- “Salvar na minha conta”

## Etapa 7 — Relatório completo

Seções:

- Resumo executivo;

- Linha do tempo;

- Custos totais;

- Custos por categoria;

- Mão de obra vs peças;

- Oficinas utilizadas;

- Serviços recorrentes;

- Possíveis retrabalhos;

- Quilometragem registrada;

- Eventos relevantes;

- Anexos disponíveis;

- Recomendações para inspeção pré-compra.

Importante: dados pessoais de proprietários anteriores devem ser mascarados ou omitidos.

# 3. Estrutura de Dados Básica

## 3.1. Entidades principais

Abaixo está uma estrutura lógica inicial, independente de tecnologia.

## 3.2. User

Representa pessoa física.

Campos principais:

- id;

- full_name;

- cpf;

- email;

- phone;

- password_hash;

- status;

- created_at;

- updated_at;

- email_verified_at;

- phone_verified_at;

- terms_accepted_at;

- privacy_policy_accepted_at.

Relacionamentos:

- um usuário pode ter vários veículos na garagem;

- um usuário pode registrar várias manutenções;

- um usuário pode comprar acesso a históricos;

- um usuário pode avaliar oficinas;

- um usuário pode enviar documentos de validação.

Observação: CPF deve ser único, mas o sistema precisa prever casos de alteração cadastral, bloqueio e duplicidade suspeita.

## 3.3. Workshop

Representa oficina, estética automotiva ou prestador automotivo vinculado a CNPJ.

Campos principais:

- id;

- cnpj;

- legal_name;

- trade_name;

- status;

- verification_status;

- address_id;

- phone;

- email;

- website;

- whatsapp;

- description;

- created_by_user_id;

- claimed_by_user_id;

- claimed_at;

- created_at;

- updated_at.

Status possíveis:

- crowdsourced;

- claimed;

- verified;

- rejected;

- suspended;

- inactive.

Relacionamentos:

- uma oficina pode ter vários serviços;

- uma oficina pode ter várias avaliações;

- uma oficina pode ter várias métricas de ranking;

- uma oficina pode ser cadastrada por usuário cliente;

- uma oficina pode ser reivindicada pelo proprietário.

## 3.4. WorkshopUser

Representa usuários autorizados a gerenciar uma oficina.

Campos:

- id;

- workshop_id;

- user_id;

- role;

- permissions;

- status;

- created_at.

Papéis:

- owner;

- manager;

- attendant;

- mechanic;

- finance;

- viewer.

## 3.5. Vehicle

Representa o veículo, centrado na placa.

Campos principais:

- id;

- plate;

- normalized_plate;

- vin, se disponível;

- renavam_hash, se aplicável;

- brand;

- model;

- version;

- year_manufacture;

- year_model;

- color;

- fuel_type;

- vehicle_type;

- created_at;

- updated_at.

Regra importante:

- plate deve ser tratada como chave funcional principal;

- pode haver histórico de troca de placa, se o sistema quiser evoluir;

- dados sensíveis devem ser protegidos.

Relacionamentos:

- um veículo pode ter vários usuários e/ou responsáveis vinculados ao longo do tempo;

- um veículo possui várias manutenções;

- um veículo possui documentos;

- um veículo pode ter vários relatórios comprados;

- um veículo pode ter histórico transferido entre proprietários pessoa física ou pessoa jurídica.

## 3.6. UserVehicle

Representa o vínculo entre usuário, titularidade CPF/CNPJ e veículo.

Essa tabela é essencial porque o veículo não pertence tecnicamente apenas ao usuário no modelo de dados; ele possui um vínculo com um titular CPF ou CNPJ e com usuários autorizados a gerenciá-lo.

Campos:

- id;

- user_id;

- vehicle_id;

- holder_type;

- holder_document_type;

- holder_document_hash;

- holder_name_snapshot;

- company_relationship_evidence, quando o titular for CNPJ;

- holder_type pode ser individual_cpf ou company_cnpj;

- relationship_type;

- ownership_status;

- validation_status;

- is_primary_vehicle;

- garage_position;

- access_level;

- started_at;

- ended_at;

- created_at;

- updated_at.

relationship_type:

- owner;

- authorized_user;

- family_member;

- company_representative;

- buyer_in_progress;

- fleet_manager;

- previous_owner;

- other.

validation_status:

- not_started;

- pending_documents;

- under_review;

- approved;

- rejected;

- expired.

access_level:

- full_management;

- private_notes_only;

- read_only;

- limited;

- pending.

Regra:

o vínculo deve aceitar titular pessoa física (CPF) ou pessoa jurídica (CNPJ);

quando o titular for CNPJ, o usuário deve comprovar autorização ou representação da empresa;

- o primeiro vínculo ativo de garagem pode ser gratuito;

- a partir do segundo veículo ativo, aplicar paywall.

## 3.7. VehicleDocument

Representa documentos enviados para validação.

Campos:

- id;

- vehicle_id;

- user_id;

- document_type;

- file_url;

- file_hash;

- status;

- extracted_owner_name;

- extracted_owner_document;

- extracted_plate;

- reviewed_by_admin_id;

- rejection_reason;

- created_at;

- reviewed_at.

document_type:

- CRLV;

- RG;

- CNH;

- authorization_letter;

- proof_of_relationship;

- purchase_contract;

- company_document;

- other.

## 3.8. MaintenanceRecord

Representa uma manutenção ou serviço realizado no veículo.

Campos principais:

- id;

- vehicle_id;

- plate_snapshot;

- user_id;

- workshop_id;

- workshop_cnpj_snapshot;

- source;

- service_date;

- odometer;

- service_category;

- vehicle_system;

- description;

- labor_amount;

- parts_amount;

- total_amount;

- currency;

- entry_date;

- promised_delivery_date;

- actual_delivery_date;

- warranty_until;

- warranty_months;

- status;

- created_at;

- updated_at.

source:

- user_manual;

- workshop_registered;

- imported_invoice;

- admin_import;

- partner_api.

status:

- draft;

- pending_confirmation;

- confirmed;

- disputed;

- hidden;

- deleted.

Regras obrigatórias:

- labor_amount e parts_amount devem ser campos separados;

- total_amount pode ser calculado;

- não permitir registro definitivo sem segregação financeira;

- se parts_amount = 0 ou labor_amount = 0, exigir justificativa.

## 3.9. MaintenanceItem

Representa os itens específicos dentro da manutenção.

Campos:

- id;

- maintenance_record_id;

- item_type;

- name;

- brand;

- part_number;

- quantity;

- unit_amount;

- total_amount;

- condition;

- notes.

item_type:

- labor;

- part;

- fluid;

- diagnostic;

- warranty;

- discount;

- other.

condition:

- new;

- used;

- refurbished;

- customer_supplied;

- not_applicable.

## 3.10. MaintenanceAttachment

Arquivos vinculados à manutenção.

Campos:

- id;

- maintenance_record_id;

- file_type;

- file_url;

- file_hash;

- visibility;

- uploaded_by_user_id;

- created_at.

file_type:

- invoice;

- service_order;

- photo_before;

- photo_after;

- receipt;

- report;

- warranty;

- other.

visibility:

- private;

- visible_to_owner;

- visible_in_paid_report;

- admin_only.

## 3.11. WorkshopReview

Avaliação subjetiva feita pelo cliente.

Campos:

- id;

- maintenance_record_id;

- workshop_id;

- user_id;

- pre_sale_rating;

- budget_clarity_rating;

- communication_rating;

- post_sale_rating;

- recommendation_rating;

- public_comment;

- private_comment;

- created_at.

Regra:

- a avaliação subjetiva deve ter peso minoritário;

- idealmente deve estar vinculada a manutenção real para evitar avaliações falsas.

## 3.12. ReworkSignal

Representa possível retrabalho identificado pelo sistema.

Campos:

- id;

- vehicle_id;

- original_maintenance_record_id;

- subsequent_maintenance_record_id;

- workshop_id;

- detected_by;

- rework_type;

- confidence_score;

- status;

- user_confirmation;

- admin_review_status;

- created_at;

- updated_at.

detected_by:

- system;

- user_report;

- workshop_report;

- admin.

rework_type:

- same_service_same_workshop;

- same_service_different_workshop;

- same_system_recurrence;

- warranty_return;

- unresolved_problem;

- repeated_part_replacement.

status:

- suspected;

- confirmed;

- rejected;

- under_review.

Regra:

- nem todo retorno é retrabalho;

- o sistema deve considerar janela temporal, quilometragem, categoria, sistema afetado e justificativas.

## 3.13. WorkshopRankingMetric

Tabela agregada para performance da oficina.

Campos:

- id;

- workshop_id;

- service_category;

- region;

- period_start;

- period_end;

- sample_size;

- price_score;

- time_score;

- rework_score;

- service_rating_score;

- confidence_score;

- objective_score;

- final_score;

- created_at.

Essa tabela permite calcular ranking por:

- geral;

- cidade;

- tipo de serviço;

- tipo de veículo;

- faixa de preço;

- período.

## 3.14. HistoryAccessPurchase

Compra de acesso ao histórico de uma placa.

Campos:

- id;

- user_id;

- vehicle_id;

- plate_snapshot;

- access_type;

- price;

- currency;

- years_unlocked;

- records_unlocked;

- access_starts_at;

- access_expires_at;

- payment_id;

- created_at.

access_type:

- fixed_report;

- yearly_history;

- full_history;

- subscription_access;

- seller_shared_access.

## 3.15. Payment

Campos:

- id;

- user_id;

- payment_provider;

- payment_type;

- amount;

- currency;

- status;

- external_payment_id;

- paid_at;

- created_at.

payment_type:

- additional_vehicle;

- vehicle_history_report;

- workshop_subscription;

- premium_garage;

- other.

## 3.16. Relacionamentos principais

Modelo simplificado:

- User 1:N UserVehicle;

- Vehicle 1:N UserVehicle;

- Vehicle 1:N MaintenanceRecord;

- Workshop 1:N MaintenanceRecord;

- MaintenanceRecord 1:N MaintenanceItem;

- MaintenanceRecord 1:N MaintenanceAttachment;

- MaintenanceRecord 1:1 ou 1:N WorkshopReview;

- Vehicle 1:N ReworkSignal;

- Workshop 1:N WorkshopRankingMetric;

- User 1:N HistoryAccessPurchase;

- Vehicle 1:N HistoryAccessPurchase;

- User 1:N Payment.

A lógica central é:

O usuário acessa o veículo por meio de um vínculo validado, mas o histórico pertence à placa/veículo.

# 4. Wireframes — Telas Críticas

## 4.1. Tela crítica 1 — Dashboard do Veículo

## Objetivo da tela

Ser o centro operacional do dono do veículo.

O usuário deve conseguir responder rapidamente:

- Qual é o estado do meu veículo?

- Quando foi a última manutenção?

- Quanto gastei?

- Onde fiz serviços?

- O que preciso fazer agora?

- Quais documentos tenho guardados?

- Posso compartilhar esse histórico para venda?

## Layout desktop

### 4.1.1. Header global

Topo fixo com:

- logo;

- menu:

- Garagem;

- Consultar placa;

- Oficinas;

- Histórico;

- Pagamentos;

- ícone de notificações;

- avatar do usuário.

CTA persistente:

- “Adicionar manutenção”.

## 4.1.2. Breadcrumb

Acima do conteúdo:

- Garagem > Honda Civic 2020 > Dashboard

Ajuda o usuário a não se perder, principalmente se tiver mais de um veículo.

## 4.1.3. Bloco principal do veículo

Card grande no topo.

Elementos:

- Foto ou ilustração do veículo;

- Placa em destaque;

- Marca/modelo/ano;

- Status:

- Validado;

- Em análise;

- Pendente;

- Rejeitado;

- Quilometragem mais recente;

- Última atualização;

- Selo:

- “Histórico vinculado à placa”.

Botões:

- “Adicionar manutenção”;

- “Enviar documento”;

- “Compartilhar histórico”;

- “Gerar relatório de venda”.

Se validação pendente:

- Banner:

- “Seu vínculo com este veículo ainda está em análise. Algumas funções estão limitadas.”

## 4.1.4. Cards de resumo

Logo abaixo do card principal, quatro cards.

### Card 1 — Última manutenção

Mostra:

- data;

- serviço;

- oficina;

- valor total;

- CTA “Ver detalhes”.

### Card 2 — Gasto total

Mostra:

- total gasto no período;

- divisão visual:

- mão de obra;

- peças;

- filtro:

- 12 meses;

- 24 meses;

- todo o histórico.

### Card 3 — Próxima manutenção

Mostra:

- recomendação;

- prazo ou quilometragem;

- nível de urgência;

- CTA “Agendar ou buscar oficina”.

### Card 4 — Saúde do histórico

Mostra:

- quantidade de registros;

- período coberto;

- completude:

- baixa;

- média;

- alta;

- documentos anexados.

## 4.1.5. Linha do tempo de manutenção

Seção principal.

Título:

- “Histórico de manutenção”

Controles:

- filtro por período;

- filtro por categoria;

- filtro por oficina;

- filtro por valor;

- alternância:

- timeline;

- tabela.

Cada evento da timeline:

- ícone da categoria;

- data;

- quilometragem;

- nome do serviço;

- oficina;

- valor mão de obra;

- valor peças;

- valor total;

- selo “com nota fiscal”;

- selo “garantia”;

- possível alerta:

- “serviço repetido em curto período”;

- “possível retrabalho”;

- “retorno em garantia”.

Ações no evento:

- “Ver detalhes”;

- “Editar”;

- “Anexar documento”;

- “Reportar problema”.

## 4.1.6. Gráfico de custos

Seção lateral ou abaixo da timeline.

Visualizações:

- custo por mês;

- custo por categoria;

- mão de obra vs peças;

- oficinas mais utilizadas.

UX importante:

- Não sobrecarregar;

- Começar com insights simples:

- “Você gastou mais com suspensão nos últimos 12 meses.”

- “Peças representam 62% dos custos deste veículo.”

## 4.1.7. Alertas inteligentes

Card lateral.

Exemplos:

- “Óleo próximo do prazo recomendado”;

- “Pneus sem registro há mais de 18 meses”;

- “Freios revisados há 14 meses”;

- “Serviço de suspensão repetido em menos de 90 dias”.

Cada alerta deve ter:

- explicação curta;

- CTA;

- possibilidade de dispensar.

## 4.1.8. Documentos do veículo

Card ou aba.

Itens:

- CRLV;

- notas fiscais;

- ordens de serviço;

- laudos;

- garantias;

- fotos.

Estados:

- documento validado;

- documento pendente;

- documento expirado;

- documento rejeitado.

## 4.1.9. Bloco de compartilhamento

Título:

- “Vai vender este veículo?”

Texto:

Gere um relatório organizado com o histórico de manutenção da placa para aumentar a confiança do comprador.

Botões:

- “Gerar relatório”

- “Criar link compartilhável”

Controle de privacidade:

- ocultar dados pessoais;

- ocultar valores;

- mostrar apenas eventos;

- expirar link em X dias.

## 4.1.10. Paywall contextual no dashboard

Se o usuário tenta adicionar segundo veículo:

Banner:

Sua garagem gratuita inclui 1 veículo. Adicione mais veículos para acompanhar históricos separados por placa.

Botão:

- “Adicionar veículo extra”

Se tenta acessar histórico completo de veículo não validado ou comprado:

Banner:

Existe histórico adicional desta placa. Desbloqueie o relatório completo para visualizar registros anteriores.

Botão:

- “Ver opções de acesso”

## Layout mobile

No mobile, a ordem deve ser:

- Placa e status;

- CTAs principais;

- Cards resumidos em carrossel;

- Alertas;

- Timeline;

- Custos;

- Documentos;

- Compartilhamento.

Botão flutuante:

- “+ Manutenção”

# 4.2. Tela crítica 2 — Perfil/Ranking da Oficina

## Objetivo da tela

Permitir que o cliente escolha uma oficina com base em critérios objetivos e comparáveis, e permitir que a oficina entenda sua reputação.

A tela precisa evitar a lógica simplista de “5 estrelas” e explicar que a nota é composta por dados operacionais.

## Layout desktop

### 4.2.1. Header da oficina

Card superior com:

- nome fantasia;

- razão social em texto menor;

- CNPJ verificado;

- selo:

- “CNPJ verificado”;

- “Perfil reivindicado”;

- “Dados em formação”, se amostra pequena;

- endereço;

- telefone;

- WhatsApp;

- website;

- horário de funcionamento;

- fotos.

CTAs:

- “Solicitar orçamento”;

- “Registrar serviço feito aqui”;

- “Salvar oficina”;

- “Compartilhar”.

## 4.2.2. Nota principal

Elemento visual de destaque.

Exemplo:

- Nota objetiva: 87/100;

- Classificação:

- Excelente;

- Muito boa;

- Boa;

- Regular;

- Dados insuficientes.

Texto explicativo:

Esta nota considera preço, prazo, retrabalho e atendimento. As avaliações de clientes têm peso menor que os dados objetivos de serviços registrados.

Evitar mostrar apenas estrelas como elemento principal.

## 4.2.3. Breakdown da nota

Quatro cards principais:

### Competitividade de preço

Mostra:

- score;

- comparação com mercado local;

- texto:

- “Mão de obra 8% abaixo da mediana regional para serviços similares.”

- separar:

- mão de obra;

- peças.

### Tempo de finalização

Mostra:

- prazo médio;

- cumprimento de prazo;

- comparação com oficinas similares.

### Taxa de retrabalho

Mostra:

- percentual;

- nível de confiança;

- explicação:

- “Calculado a partir de retornos ou serviços semelhantes na mesma placa em curto período.”

### Atendimento

Mostra:

- avaliação média de pré-venda;

- pós-venda;

- clareza do orçamento;

- comunicação.

## 4.2.4. Ranking por categoria

Tabela:

| Categoria | Nota | Preço | Prazo | Retrabalho | Amostra |
| --- | --- | --- | --- | --- | --- |
| Freios | 91 | 88 | 90 | 95 | 42 |
| Suspensão | 84 | 81 | 86 | 83 | 29 |
| Revisão | 89 | 87 | 92 | 88 | 64 |

Importante: oficinas podem ser excelentes em uma categoria e medianas em outra.

## 4.2.5. Comparativo com mercado

Gráficos simples:

- preço médio da oficina vs mediana regional;

- prazo médio vs mediana regional;

- retrabalho vs média regional.

Nunca apresentar isso de forma acusatória. Usar linguagem analítica.

Exemplo:

Esta oficina tende a ter preços acima da mediana, mas apresenta baixa taxa de retrabalho.

## 4.2.6. Serviços populares

Lista:

- troca de óleo;

- revisão preventiva;

- freios;

- suspensão;

- estética;

- diagnóstico.

Cada serviço pode mostrar:

- preço típico de mão de obra;

- faixa de peças, quando comparável;

- tempo médio;

- índice de satisfação.

## 4.2.7. Avaliações de clientes

As avaliações aparecem, mas em posição secundária.

Elementos:

- nota média de atendimento;

- comentários;

- filtro por serviço;

- indicação se avaliação está vinculada a manutenção real.

Selo:

- “Avaliação verificada por serviço registrado.”

## 4.2.8. Transparência do algoritmo

Card educativo:

Como calculamos este ranking?

Resumo:

- Preço competitivo;

- Tempo de conclusão;

- Baixa taxa de retrabalho;

- Atendimento ao cliente;

- Volume de dados;

- Comparação com oficinas similares.

CTA:

- “Entender metodologia”

Isso aumenta confiança e reduz sensação de arbitrariedade.

## 4.2.9. Estado de amostra baixa

Se a oficina tiver poucos registros:

Não mostrar nota definitiva.

Mensagem:

Ainda não há dados suficientes para uma nota conclusiva. Esta oficina possui 4 serviços registrados. A nota ficará mais precisa a partir de 15 registros comparáveis.

Mostrar:

- dados disponíveis;

- status “em formação”;

- CTA para clientes registrarem manutenções.

## 4.2.10. Visão da própria oficina

Quando a oficina logada vê seu perfil, adicionar painel privado:

- “Sua posição no ranking”;

- “Como melhorar sua nota”;

- “Dados incompletos que prejudicam sua avaliação”;

- “Serviços aguardando confirmação do cliente”;

- “Possíveis retrabalhos em análise”.

Exemplos de recomendações:

- “Registre data prometida e data real para melhorar a métrica de prazo.”

- “Separe corretamente mão de obra e peças.”

- “Confirme serviços finalizados para aumentar sua amostra.”

- “Responda avaliações de atendimento.”

# 5. Lógica Matemática para Ranking

## 5.1. Premissas

A nota da oficina deve ser:

- objetiva;

- comparável;

- resistente a manipulação;

- explicável;

- ajustada por categoria de serviço;

- ajustada por região;

- ajustada por volume de dados;

- menos dependente de estrelas;

- mais dependente de performance real.

A nota não deve comparar oficinas de forma bruta. Uma oficina especializada em motor não deve ser comparada diretamente com estética automotiva ou troca de óleo simples.

A comparação deve considerar:

- categoria de serviço;

- cidade/região;

- tipo de veículo;

- complexidade;

- faixa de preço;

- volume de dados.

## 5.2. Componentes da nota

Sugestão de pesos:

- Competitividade de preço: 30%;

- Tempo de finalização: 25%;

- Taxa de retrabalho: 30%;

- Avaliação subjetiva de atendimento: 15%.

Fórmula base:

Nota_Final = 
 0,30 × Score_Preco + 
 0,25 × Score_Tempo + 
 0,30 × Score_Retrabalho + 
 0,15 × Score_Atendimento

Depois, aplicar fator de confiança:

Nota_Final_Ajustada = Nota_Final × Fator_Confianca

Ou, de forma mais elegante, usar o fator de confiança para aproximar a nota da média do mercado quando houver poucos dados:

Nota_Final_Ajustada = 
 (Nota_Final × Fator_Confianca) + 
 (Media_Mercado × (1 - Fator_Confianca))

Isso evita que uma oficina com dois serviços perfeitos apareça acima de uma oficina com centenas de registros consistentes.

## 5.3. Score de preço

O preço deve ser calculado comparando a oficina com oficinas similares.

### Separação obrigatória

O sistema deve calcular separadamente:

- preço de mão de obra;

- preço de peças.

Isso é essencial porque uma oficina pode ter mão de obra cara e peças baratas, ou o inverso.

### Fórmula sugerida

Para cada manutenção:

Preco_Total_Normalizado = 
 Peso_Mao_de_Obra × Score_Mao_de_Obra + 
 Peso_Pecas × Score_Pecas

Sugestão:

- mão de obra: 70%;

- peças: 30%.

Mas isso pode variar por categoria.

Exemplo:

- estética automotiva: mão de obra pesa mais;

- troca de peças: peças pesam mais;

- diagnóstico: mão de obra pesa quase tudo.

### Cálculo por percentil

Para cada categoria e região, calcular a posição da oficina em relação à mediana.

Exemplo:

Indice_Preco_Mao_de_Obra = 
 Valor_Mao_de_Obra_Oficina / Mediana_Mao_de_Obra_Mercado

Interpretação:

- 0,90 = 10% mais barata que a mediana;

- 1,00 = igual à mediana;

- 1,20 = 20% mais cara que a mediana.

Conversão para score:

Score_Preco = 100 - Penalidade_Preco

Uma lógica simples:

Se Indice_Preco <= 0,85: Score = 100 
Se Indice_Preco entre 0,85 e 1,00: Score = 90 a 100 
Se Indice_Preco entre 1,00 e 1,20: Score = 70 a 90 
Se Indice_Preco entre 1,20 e 1,50: Score = 40 a 70 
Se Indice_Preco > 1,50: Score = 0 a 40

Cuidado: a oficina mais barata não deve ser automaticamente a melhor. Preço muito abaixo do mercado pode indicar baixa qualidade ou peça inferior. Por isso, o score de preço deve ser combinado com retrabalho.

## 5.4. Score de tempo

O tempo deve considerar:

- data de entrada;

- data prometida;

- data real de entrega;

- tipo de serviço;

- complexidade;

- cumprimento do prazo informado;

- comparação com oficinas semelhantes.

### Métricas úteis

Tempo_Execucao = Data_Entrega_Real - Data_Entrada

Atraso = Data_Entrega_Real - Data_Prometida

Taxa_Cumprimento_Prazo = 
 Serviços_Entregues_No_Prazo / Serviços_Com_Data_Prometida

### Fórmula sugerida

Score_Tempo = 
 0,60 × Score_Tempo_vs_Mercado + 
 0,40 × Score_Cumprimento_Prazo

Onde:

- Score_Tempo_vs_Mercado compara o tempo médio da oficina com a mediana da categoria;

- Score_Cumprimento_Prazo mede se a oficina cumpre o que promete.

Isso evita premiar uma oficina que promete prazo longo demais apenas para sempre cumprir.

## 5.5. Score de retrabalho

Este deve ser um dos fatores mais importantes, porque indica qualidade real.

## Definição de possível retrabalho

O sistema deve marcar possível retrabalho quando ocorrer:

- mesma placa;

- mesmo sistema do veículo;

- serviço igual ou similar;

- intervalo curto;

- retorno à mesma oficina ou ida a outra oficina para corrigir problema;

- relato do usuário indicando que o problema persistiu;

- acionamento de garantia.

Exemplo:

Troca de pastilhas em 10/03 
Novo serviço de freio em 25/03 
Mesmo veículo 
Mesmo sistema 
Intervalo de 15 dias 
Possível retrabalho

## Janelas temporais sugeridas

A janela depende da categoria:

- troca de óleo: 7 a 30 dias;

- freios: 30 a 90 dias;

- suspensão: 30 a 120 dias;

- motor: 30 a 180 dias;

- elétrica: 15 a 90 dias;

- estética: 7 a 30 dias;

- pintura/funilaria: 30 a 180 dias.

## Fórmula simples

Taxa_Retrabalho = 
 Retrabalhos_Confirmados / Serviços_Comparáveis

Converter em score:

Score_Retrabalho = 100 × (1 - Taxa_Retrabalho_Ajustada)

Mas é melhor aplicar suavização bayesiana:

Taxa_Retrabalho_Ajustada = 
 (Retrabalhos_Confirmados + Retrabalho_Medio_Mercado × K) / 
 (Serviços_Comparáveis + K)

Onde:

- K é um fator de suavização;

- quanto menor a amostra, mais a taxa se aproxima da média do mercado;

- quanto maior a amostra, mais a taxa real da oficina prevalece.

Exemplo:

K = 20

Isso evita distorções quando a oficina tem poucos serviços registrados.

## 5.6. Score de atendimento

A avaliação subjetiva deve entrar com peso menor.

Campos avaliados:

- pré-venda;

- clareza do orçamento;

- comunicação;

- pós-venda;

- recomendação.

Fórmula:

Score_Atendimento = 
 Media_Avaliacoes_Atendimento / 5 × 100

Ou mais detalhado:

Score_Atendimento = 
 0,25 × Pre_Venda + 
 0,25 × Clareza_Orcamento + 
 0,25 × Comunicacao + 
 0,25 × Pos_Venda

Depois converter para escala 0 a 100.

Avaliações não vinculadas a uma manutenção real devem ter peso menor ou não entrar na nota principal.

## 5.7. Fator de confiança

A nota precisa considerar a quantidade e qualidade dos dados.

Variáveis:

- número de serviços registrados;

- número de serviços confirmados por cliente;

- número de documentos anexados;

- diversidade de clientes;

- consistência dos dados;

- idade dos dados;

- completude dos campos obrigatórios.

Fórmula simples:

Fator_Confianca = min(1, log(1 + N) / log(1 + N_Referencia))

Onde:

- N = número de serviços válidos;

- N_Referencia = quantidade considerada suficiente, por exemplo 50.

Exemplo:

Fator_Confianca = min(1, log(1 + Serviços_Validos) / log(51))

Classificação:

- 0 a 0,30: dados insuficientes;

- 0,31 a 0,60: dados em formação;

- 0,61 a 0,80: boa confiabilidade;

- 0,81 a 1,00: alta confiabilidade.

## 5.8. Fórmula final recomendada

Score_Objetivo = 
 0,35 × Score_Retrabalho + 
 0,30 × Score_Preco + 
 0,25 × Score_Tempo + 
 0,10 × Score_Consistencia_Dados

Score_Final_Bruto = 
 0,85 × Score_Objetivo + 
 0,15 × Score_Atendimento

Score_Final_Ajustado = 
 (Score_Final_Bruto × Fator_Confianca) + 
 (Media_Mercado × (1 - Fator_Confianca))

Sugestão prática:

- Exibir a nota final ajustada;

- Exibir o fator de confiança;

- Exibir a amostra usada;

- Exibir ranking por categoria.

## 5.9. Exemplo prático

Oficina A:

- Score preço: 82;

- Score tempo: 90;

- Score retrabalho: 76;

- Score consistência: 88;

- Score atendimento: 94;

- Fator confiança: 0,72;

- Média do mercado: 75.

Cálculo:

Score_Objetivo = 
 0,35×76 + 0,30×82 + 0,25×90 + 0,10×88

Score_Objetivo = 
 26,6 + 24,6 + 22,5 + 8,8 = 82,5

Score_Final_Bruto = 
 0,85×82,5 + 0,15×94

Score_Final_Bruto = 
 70,125 + 14,1 = 84,225

Score_Final_Ajustado = 
 84,225×0,72 + 75×0,28

Score_Final_Ajustado = 
 60,642 + 21 = 81,642

Nota exibida:

82/100

# 6. Estratégia de Paywall com Baixa Fricção

## 6.1. Paywall para segundo veículo

Não deve aparecer no primeiro contato com o produto.

Fluxo ideal:

- usuário entende o valor da garagem;

- cadastra primeiro veículo gratuitamente;

- usa dashboard;

- tenta adicionar segundo veículo;

- vê benefícios concretos;

- paga para expandir.

Mensagem sugerida:

Sua garagem gratuita inclui 1 veículo. Para acompanhar outro carro com histórico, documentos e alertas separados por placa, adicione um veículo extra.

CTAs:

- “Adicionar veículo extra”

- “Ver planos”

- “Agora não”

Evitar linguagem punitiva como:

- “Você atingiu o limite.”

- “Bloqueado.”

- “Plano insuficiente.”

Preferir linguagem de expansão:

- “Expanda sua garagem.”

- “Adicione mais um veículo.”

- “Organize outro histórico.”

## 6.2. Paywall para histórico completo

Deve vir depois de uma prévia forte.

Antes de cobrar, mostrar:

- que há dados;

- quantos registros existem;

- quais anos estão cobertos;

- quais categorias existem;

- se há possíveis alertas;

- se há oficinas registradas;

- se há documentos disponíveis.

Exemplo:

Encontramos 22 registros de manutenção para esta placa, cobrindo o período de 2020 a 2026. O relatório inclui custos, oficinas, peças, mão de obra e possíveis recorrências de serviço.

CTA:

- “Desbloquear histórico completo”

## 6.3. Paywall variável por profundidade de histórico

O preço pode considerar:

- quantidade de anos;

- quantidade de registros;

- existência de documentos anexos;

- nível de completude;

- finalidade:

- consulta simples;

- relatório para compra;

- relatório premium.

Exemplo de planos:

### Consulta básica

- eventos resumidos;

- categorias;

- datas;

- sem anexos;

- menor preço.

### Relatório completo

- linha do tempo;

- custos;

- oficinas;

- peças;

- mão de obra;

- possíveis retrabalhos.

### Relatório premium

- relatório em PDF;

- análise de risco;

- recomendações para vistoria;

- compartilhamento com terceiros.

# 7. Regras de UX e Confiança

## 7.1. Transparência

O usuário deve sempre entender:

- por que precisa enviar documento;

- por que precisa pagar;

- como a nota da oficina é calculada;

- o que será público;

- o que será privado;

- o que será usado no ranking.

## 7.2. Privacidade

Dados pessoais não devem aparecer em relatórios públicos ou pagos.

Mas podem aparecer:

- dados da placa;

- histórico de manutenção;

- oficinas;

- valores;

- categorias;

- peças;

- datas;

- quilometragens;

- documentos com dados mascarados, se autorizado.

## 7.3. Evitar abuso por oficinas

Riscos:

- oficina lançar serviços falsos;

- oficina manipular preço;

- oficina cadastrar cliente sem autorização;

- oficina tentar excluir retrabalho;

- oficina pedir avaliações positivas.

Mitigações:

- confirmação do cliente;

- anexos;

- validação por nota ou ordem de serviço;

- auditoria;

- peso maior para registros confirmados;

- detecção de padrões suspeitos;

- limitação de autoavaliação;

- sinalização de dados não confirmados.

## 7.4. Evitar abuso por usuários

Riscos:

- usuário cadastrar oficina errada;

- usuário registrar manutenção falsa;

- usuário avaliar oficina sem serviço real;

- usuário tentar acessar histórico de veículo sem legitimidade.

Mitigações:

- vínculo com placa;

- CNPJ obrigatório;

- anexos;

- moderação;

- confirmação cruzada;

- peso maior para registros comprovados;

- avaliações apenas vinculadas a manutenção.

# 8. MVP Recomendado

## 8.1. MVP Cliente

Funcionalidades essenciais:

- cadastro de cliente com CPF e suporte a vínculo por CNPJ quando o veículo pertencer a empresa;

- garagem;

- primeiro veículo gratuito;

- cadastro de veículo por placa;

- upload de CRLV;

- status de validação;

- cadastro manual de manutenção;

- separação mão de obra e peças;

- histórico em timeline;

- avaliação da oficina;

- consulta de histórico por placa;

- paywall para histórico completo;

- paywall para segundo veículo.

## 8.2. MVP Oficina

Funcionalidades essenciais:

- cadastro com CNPJ;

- perfil público;

- reivindicação de oficina crowdsourced;

- registro de serviço;

- painel de serviços;

- métricas básicas;

- ranking inicial por categoria;

- recebimento de avaliações.

## 8.3. MVP Ranking

Começar com:

- preço;

- prazo;

- retrabalho provável;

- avaliação subjetiva;

- fator de confiança;

- nota por categoria.

Evitar no MVP:

- machine learning complexo;

- precificação dinâmica sofisticada;

- OCR avançado obrigatório;

- integrações profundas com sistemas de oficina;

- ranking nacional generalista sem dados suficientes.

# 9. Roadmap Evolutivo

## Fase 1 — Fundação

- Cadastro cliente;

- Cadastro oficina;

- Placa como entidade central;

- Histórico manual;

- Paywall simples;

- Ranking inicial.

## Fase 2 — Qualidade dos dados

- OCR de documentos;

- validação mais robusta de CRLV;

- nota fiscal;

- ordem de serviço;

- confirmação cruzada cliente/oficina;

- detecção aprimorada de retrabalho.

## Fase 3 — Marketplace

- Solicitação de orçamento;

- comparação entre oficinas;

- agendamento;

- pagamento de serviços;

- garantia digital.

## Fase 4 — Inteligência

- previsão de manutenção;

- alertas personalizados;

- análise de risco para compra de usado;

- score de histórico do veículo;

- benchmarking avançado de oficinas.

## Fase 5 — Integrações

- ERPs de oficinas;

- seguradoras;

- vistoriadoras;

- marketplaces de veículos;

- financeiras;

- plataformas de compra e venda.

# 10. Métricas de Produto

## 10.1. Métricas cliente

- taxa de cadastro;

- taxa de primeiro veículo cadastrado;

- taxa de validação de CRLV;

- taxa de conclusão de manutenção;

- número médio de manutenções por veículo;

- conversão para segundo veículo;

- conversão no paywall de histórico;

- downloads de relatório;

- compartilhamentos de histórico.

## 10.2. Métricas oficina

- oficinas cadastradas;

- oficinas verificadas;

- oficinas reivindicadas;

- serviços registrados;

- serviços confirmados por clientes;

- avaliações recebidas;

- taxa de preenchimento completo;

- uso do dashboard de ranking.

## 10.3. Métricas de dados

- percentual de manutenções com CNPJ;

- percentual com mão de obra e peças separados;

- percentual com data prometida e data real;

- percentual com anexos;

- taxa de registros confirmados;

- taxa de possíveis retrabalhos;

- cobertura média de histórico por placa.

## 10.4. Métricas de monetização

- conversão para veículo adicional;

- conversão para histórico pago;

- receita por consulta;

- receita média por usuário;

- taxa de recompra de relatórios;

- abandono no checkout;

- taxa de chargeback.

# 11. Conclusão de Produto

O diferencial do Web App não deve ser apenas “avaliar oficinas”, mas criar uma infraestrutura confiável de dados automotivos.

A proposta de valor central é:

Para o dono do veículo, o app organiza e protege o histórico real do carro. 
Para o comprador de usado, reduz risco e melhora a tomada de decisão. 
Para a oficina, cria reputação objetiva baseada em performance. 
Para o mercado, transforma a placa em uma linha do tempo confiável de manutenção.

O sucesso do produto dependerá de três pontos:

- **Baixa fricção de cadastro**, especialmente no primeiro veículo;

- **Alta confiança nos dados**, com CNPJ, CPF, placa, documentos e confirmação cruzada;

- **Ranking explicável**, no qual a oficina entende como melhorar e o cliente entende por que confiar.
