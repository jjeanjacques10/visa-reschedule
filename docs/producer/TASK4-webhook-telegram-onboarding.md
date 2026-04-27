# TASK 4: LambdaWebhookHandler (Telegram + Onboarding)

## Objetivo

Implementar a Lambda de webhook para processar mensagens do Telegram e conduzir o onboarding/state machine por usuário.

## Escopo

1. Criar handler HTTP (API Gateway -> Lambda).
2. Parsear update do Telegram e extrair `chat_id` e texto.
3. Implementar máquina de estados:
   - `WAITING_EMAIL`
   - `WAITING_PASSWORD`
   - `WAITING_CURRENT_DATE`
   - `WAITING_DESIRED_DATE`
   - `WAITING_CITY`
   - `WAITING_CONFIRMATION`
   - `ACTIVE`
4. Implementar comandos:
   - `/iniciar`, `/ajuda`, `/status`, `/pausar`, `/retomar`, `/alterar_data`, `/alterar_cidade`, `/parar`
5. Enviar respostas para Telegram (`sendMessage`) conforme estado/comando.
6. Persistir transições e dados no DynamoDB.

## Entregáveis

- [ ] `internal/app/webhook_handler.go`
- [ ] `internal/services/onboarding_service.go`
- [ ] `internal/services/command_service.go`
- [ ] `internal/integrations/telegram_client.go`
- [ ] testes unitários para transições principais

## Critérios de Aceite

- Primeiro contato inicia fluxo corretamente.
- Usuário consegue completar onboarding até confirmação final.
- Comandos de status/pausa/retomada funcionam em usuário já ativo.
- Erros de entrada retornam mensagens orientativas (sem quebrar estado).

## Dependências

- TASK 1
- TASK 2
- TASK 3

## Fora de Escopo

- Disparo periódico EventBridge.
