# telegram-bot-producer

Aplicacao em Go para receber webhook do Telegram, conduzir onboarding de usuarios, persistir estado e publicar mensagens na fila SQS usada pelo worker de reagendamento.

## Visao geral

O projeto possui dois entrypoints principais:

- `webhook`: processa updates do Telegram (`/webhook/telegram`) e executa onboarding/comandos.
- `scheduler`: recebe evento agendado (EventBridge) e reenfileira usuarios ativos para consulta.

Fluxo simplificado:

```text
Telegram -> Webhook Handler -> DynamoDB / SQS
EventBridge -> Scheduled Dispatcher -> DynamoDB -> SQS
```

## Estrutura do repositorio

```text
app/                    # modulo Go
	cmd/                  # binarios (webhook, scheduler)
	internal/             # dominio, servicos, integracoes, handlers
docs/                   # especificacao e runbooks
infrastructure/terraform/ # infraestrutura AWS com Terraform
local-environment/      # LocalStack + scripts de bootstrap local
```

## Pre-requisitos

- Go 1.24+
- Docker e Docker Compose
- AWS CLI
- Bash (Git Bash/WSL no Windows)

## Variaveis de ambiente

Use o arquivo de exemplo em `app/.env.local.example`.

Variaveis obrigatorias para executar a aplicacao:

- `TELEGRAM_BOT_TOKEN`
- `SQS_QUEUE_URL`
- `DYNAMODB_TABLE`
- `AES_SECRET_KEY` (minimo de 8 caracteres)

Variaveis opcionais:

- `AWS_ENDPOINT_URL` (ex.: `http://localhost:4566`)
- `AWS_REGION` (padrao: `us-east-1`)
- `HTTP_PORT` (padrao: `8080`)

## Build e testes

```bash
cd app
go test ./...
go build ./cmd/webhook
go build ./cmd/scheduler
```

## Execucao local

1. Criar arquivo de ambiente na raiz do repositorio:

```bash
cp app/.env.local.example .env.local
```

2. Subir LocalStack e criar recursos locais (SQS, DynamoDB e regra EventBridge):

```bash
./local-environment/scripts/start.sh
```

3. Em outro terminal, iniciar o webhook local:

```bash
cd app
set -a; source ../.env.local; set +a
go run ./cmd/webhook
```

4. Enviar payload de teste para o endpoint:

```bash
./local-environment/scripts/send_test_message.sh
```

## Validacao rapida do ambiente local

```bash
aws --endpoint-url http://localhost:4566 sqs list-queues
aws --endpoint-url http://localhost:4566 dynamodb list-tables
```

## Documentacao

- `docs/SPEC-telegram-bot-producer.md`: especificacao funcional e arquitetura.
- `docs/producer/`: tarefas e runbook operacional.
