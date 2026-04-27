# Runbook Operacional - Telegram Bot Producer

## Alarmes mínimos
- Lambda scheduler errors >= 1
- Falha de envio Telegram/SQS observada em logs estruturados

## Checklist de deploy
1. `terraform validate`
2. `go test ./...`
3. Empacotar binários `webhook` e `scheduler`
4. `terraform plan -var-file=env.tfvars`
5. `terraform apply`

## Incidentes
- **SQS indisponível**: pausar monitoramento para usuários afetados e reprocessar scheduler.
- **Telegram API falhando**: validar token e limites de rate.
- **DynamoDB throttling**: reduzir batch do scheduler e revisar capacity/modo on-demand.
