# TASK 2: Contratos e Modelagem de Dados

## Objetivo

Definir os contratos de entrada/saída e os modelos de domínio que serão utilizados pelo producer.

## Escopo

1. Modelar contrato do webhook do Telegram (`update_id`, `message.chat.id`, `message.text`, etc).
2. Modelar contrato do evento EventBridge (`source`, `detail-type`, `detail`).
3. Modelar contrato da mensagem publicada na SQS (`visa-reschedule-queue`).
4. Definir estados da state machine de onboarding.
5. Definir validações de negócio essenciais (datas, obrigatoriedade, consistência).

## Entregáveis

- [ ] `internal/contracts/telegram_update.go`
- [ ] `internal/contracts/eventbridge_event.go`
- [ ] `internal/contracts/sqs_message.go`
- [ ] `internal/domain/onboarding_state.go`
- [ ] `internal/domain/user.go`
- [ ] `internal/domain/validation.go`
- [ ] testes unitários dos contratos/validações

## Critérios de Aceite

- Parse de payload Telegram de exemplo funciona.
- Parse de payload EventBridge de exemplo funciona.
- Serialização de mensagem SQS segue formato da SPEC.
- Regras de data inválida e `desired < current` são validadas por teste.

## Dependências

- TASK 1.

## Fora de Escopo

- Persistência em DynamoDB.
- Handlers Lambda completos.
