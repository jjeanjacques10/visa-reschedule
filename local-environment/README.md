# Ambiente local

1. `cp ../.env.local.example ../.env.local`
2. `./scripts/start.sh`
3. `./scripts/run_webhook_local.sh`
4. `./scripts/send_test_message.sh`

Validação:

```bash
aws --endpoint-url http://localhost:4566 sqs list-queues
aws --endpoint-url http://localhost:4566 dynamodb list-tables
```
