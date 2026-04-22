# TASK 8: Infraestrutura AWS em Terraform

## Objetivo

Implementar toda a infraestrutura do `telegram-bot-producer` com Terraform, alinhada ao padrão já adotado no worker.

## Escopo

1. Estruturar diretório `infrastructure/terraform/` com:
   - `main.tf`
   - `variables.tf`
   - `outputs.tf`
2. Provisionar API Gateway para webhook Telegram (`api_gateway.tf`).
3. Provisionar Lambdas `webhook` e `scheduler` (`lambda.tf`).
4. Provisionar/definir tabela DynamoDB e GSIs (`dynamodb.tf`).
5. Integrar fila SQS `visa-reschedule-queue` por referência entre stacks (`sqs.tf`).
6. Provisionar EventBridge Rule + Target (`eventbridge.tf`).
7. Provisionar IAM mínimo necessário (`iam.tf`).
8. Provisionar log groups e alarmes (`cloudwatch.tf`).
9. Definir variáveis por ambiente (`*.tfvars`) e outputs para integrações.

## Entregáveis

- [ ] `infrastructure/terraform/main.tf`
- [ ] `infrastructure/terraform/variables.tf`
- [ ] `infrastructure/terraform/outputs.tf`
- [ ] `infrastructure/terraform/api_gateway.tf`
- [ ] `infrastructure/terraform/lambda.tf`
- [ ] `infrastructure/terraform/dynamodb.tf`
- [ ] `infrastructure/terraform/sqs.tf`
- [ ] `infrastructure/terraform/eventbridge.tf`
- [ ] `infrastructure/terraform/iam.tf`
- [ ] `infrastructure/terraform/cloudwatch.tf`
- [ ] `infrastructure/terraform/terraform.tfvars.example`

## Critérios de Aceite

- `terraform init` executa sem erros.
- `terraform validate` executa sem erros.
- `terraform plan` executa sem erros com `tfvars` de exemplo.
- IAM segue princípio de menor privilégio.
- Recursos essenciais (API Gateway, Lambdas, DynamoDB, EventBridge, logs/alarms) estão codificados em `.tf`.

## Dependências

- TASK 0
- TASK 1
- TASK 3
- TASK 4
- TASK 5
- TASK 6

## Fora de Escopo

- Deploy de aplicação via pipeline CI/CD completo.
- Estratégia avançada de módulos compartilhados entre múltiplos repositórios.
