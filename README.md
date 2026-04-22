# telegram-bot-producer

Projeto Go serverless responsável por webhook Telegram, onboarding e publicação SQS.

## Build

```bash
go test ./...
go build ./cmd/webhook
go build ./cmd/scheduler
```

## Execução local

```bash
cp .env.local.example .env.local
./local-environment/scripts/start.sh
./local-environment/scripts/run_webhook_local.sh
```
