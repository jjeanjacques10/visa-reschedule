# TASK 3: Persistência DynamoDB (Usuários e Estado)

## Objetivo

Implementar a camada de persistência de usuários e estado de onboarding no DynamoDB.

## Escopo

1. Criar repositório DynamoDB para tabela `visa-rescheduler-users`.
2. Implementar operações:
   - buscar por `chat_id` (GSI `telegram-index`)
   - buscar por `portal_username` (GSI `email-index`)
   - criar usuário
   - atualizar estado e configuração
   - pausar/retomar monitoramento
3. Definir mapeamento de campos da entidade (`state`, `monitoring_enabled`, datas, cidade etc).
4. Criar definições de infraestrutura em Terraform para tabela e GSIs.

## Entregáveis

- [ ] `internal/integrations/dynamodb_repository.go`
- [ ] interface de repositório em `internal/services` ou `internal/domain`
- [ ] testes unitários com mocks
- [ ] definição de infraestrutura da tabela + GSIs em `infrastructure/terraform/dynamodb.tf`

## Critérios de Aceite

- Operações básicas de CRUD e consultas por índices cobertas por testes.
- Atualização de estado preserva consistência da state machine.
- Campos obrigatórios persistidos conforme SPEC.

## Dependências

- TASK 1
- TASK 2

## Fora de Escopo

- Handler Telegram.
- Publicação SQS.
