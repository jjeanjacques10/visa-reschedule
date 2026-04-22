# TASK 5: Publicação SQS e Disparo Inicial

## Objetivo

Implementar o producer SQS para publicação de requests ao worker e integrar com confirmação final do onboarding e comandos de retomada.

## Escopo

1. Implementar cliente SQS e serialização do payload no formato definido.
2. Publicar primeira mensagem após confirmação do usuário no onboarding.
3. Publicar nova mensagem ao `/retomar` (quando aplicável).
4. Garantir geração de `request_id` único por envio.
5. Definir estratégia de logs e tratamento de erro de publicação.

## Entregáveis

- [ ] `internal/integrations/sqs_producer.go`
- [ ] integração no fluxo de confirmação do onboarding
- [ ] integração no comando `/retomar`
- [ ] testes unitários de serialização e envio

## Critérios de Aceite

- Mensagem enviada para `visa-reschedule-queue` com campos obrigatórios.
- Erros de envio são logados e retornam resposta apropriada ao usuário.
- `client_id` segue padrão `telegram-<chat_id>`.

## Dependências

- TASK 2
- TASK 3
- TASK 4

## Fora de Escopo

- Scheduler via EventBridge.
