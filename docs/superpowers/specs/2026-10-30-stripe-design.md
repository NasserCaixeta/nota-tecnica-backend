# Substituição do Asaas pelo Stripe no piloto

Usuário escolheu Stripe em30/10/2026, possui chave e autorizou execução direta já estabelecida na sessão. Esta substituição encerra o onboarding Asaas; nenhum recurso ativo depende de conta, API, SMTP ou Sandbox Asaas. O termo interno sandbox significa ambiente de testes do provedor atual.

Stripe Checkout hospedado com cartão de teste, compra avulsa em BRL e assinatura mensal. Preservar regras720horas/cinco vagas, leitura legítima, cancelamento sem renovação e auditoria. Nenhuma chave live é aceita, e todo objeto canônico precisa declarar livemode=false. Não alterar cobrança real ou contratar serviços. Credenciais só em .env.sandbox privado.

Abordagens: substituir o adaptador e integrar os eventos Stripe, escolhida pelo usuário; manter ambos acrescentaria operação que ele não quer; formulário próprio de cartão acrescentaria escopo. Interface continua usando pedido opaco e URL autorizada de checkout.stripe.com.

Normalizar estado financeiro via API Stripe2026-10-28.endive. Compra avulsa usa PaymentIntent canônico, recorrência usa invoice canônica com pagamento, linha mensal e período daquela fatura (não período futuro atual da assinatura). Metadata server-side associa pedido/comprador e Customer.metadata identifica o usuário, sem enviar CPF ao Stripe. Refund/disputa identificados pelo PI da cobrança devem convergir para a mesma invoice/benefício recorrente, sem criar recibos duplicados. Assinatura cancelada no fim do período mantém direito pago.

Webhook valida HMAC-SHA256 Stripe-Signature sobre bytes originais, timestamp±300s, evento comlivemode=false, limite128KiB e inbox transacional antes de despacho. Checkout completo nunca concede benefício isoladamente. Idempotency-Key estável permite reconciliação da criação dentro de23horas; depois disso só recuperar ID conhecido, sem repetir POST após expiração da garantia Stripe.

Migração0018 adiciona provider ao pedido; pedidos legados ficam asaase novos stripe. Não apagar/reclassificar histórico ou alterar migrações passadas. Eventos/cancelamentos legados não são enviados ao Stripe. CPF/email continuam locais para participação; a propriedade financeira Stripe usa metadata de usuário controlada pelo servidor.

Validação: testes HTTP controlados, assinaturas inválidas/replay/live, período/cancelamento/refund/ambiguidade, PostgreSQL com upgrade desde0017, frontend e navegador. Homologação real exige chave de teste fornecida e segredo de webhook/CLI. Não confundir testes locais com execução remota.

Fontes oficiais verificadas30/10: https://docs.stripe.com/api/versioning ; https://docs.stripe.com/api/invoice-payment/list ; https://docs.stripe.com/api/invoices/object ; https://docs.stripe.com/api/subscriptions/object ; https://docs.stripe.com/events/manage-webhook-endpoints ; https://docs.stripe.com/cli .
