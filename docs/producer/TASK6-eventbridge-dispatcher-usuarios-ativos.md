# TASK 6: LambdaScheduledDispatcher (EventBridge)

## Objetivo

Implementar a Lambda acionada periodicamente por EventBridge para reenviar requests de usuários ativos à SQS.

## Escopo

1. Criar handler da Lambda de agendamento.
2. Receber e validar evento `dispatch-active-users`.
3. Buscar usuários ativos (`monitoring_enabled = true`) no DynamoDB.
4. Publicar mensagem SQS por usuário ativo.
5. Definir limites/batches para evitar timeout (paginação e throttling).
6. Criar regra do EventBridge em Terraform (`infrastructure/terraform/eventbridge.tf`).

## Entregáveis

- [ ] `internal/app/scheduled_dispatcher.go`
- [ ] lógica de paginação/varredura de ativos
- [ ] integração com `sqs_producer`
- [ ] infraestrutura da regra EventBridge em `infrastructure/terraform/eventbridge.tf`
- [ ] testes unitários do fluxo de despacho

## Critérios de Aceite

- Evento válido dispara processamento sem erro.
- Usuários pausados não são enviados.
- Usuários ativos geram mensagens SQS válidas.
- Logs mostram totais processados/sucesso/falha.

## Dependências

- TASK 3
- TASK 5

## Fora de Escopo

- Reprocessamento com DLQ específico do producer.
