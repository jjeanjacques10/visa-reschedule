# TASK 0: Ambiente Local (LocalStack + Execução Fácil da Lambda)

## Objetivo

Configurar um ambiente local simples e reproduzível para o `telegram-bot-producer`, permitindo:

- Subir dependências AWS locais via LocalStack (SQS, DynamoDB, EventBridge opcional).
- Rodar a Lambda de forma **fácil na máquina** (sem muita configuração) durante desenvolvimento.
- Testar fluxo ponta a ponta com comandos copy/paste, como no padrão já usado no worker.

## Escopo

1. **Estrutura de ambiente local**
   - Criar pasta `local-environment/` com:
     - `docker-compose.yml`
     - `scripts/start.sh`
     - `scripts/create_resources.sh`
     - `scripts/send_test_message.sh`
     - `README.md`

2. **LocalStack com bootstrap automático**
   - Subir LocalStack com serviços mínimos: `sqs,dynamodb,eventbridge,cloudwatch`.
   - Criar automaticamente recursos necessários no startup:
     - fila `visa-reschedule-queue`
     - tabela `visa-rescheduler-users` com GSIs (`telegram-index`, `email-index`)
     - regra EventBridge de exemplo (opcional no MVP)

3. **Execução local da Lambda simplificada (principal requisito)**
   - Criar modo local para execução da Lambda webhook por comando único, por exemplo:
     - `go run ./cmd/webhook`
   - Disponibilizar endpoint local HTTP para simular webhook do Telegram (ex.: `POST /webhook/telegram`).
   - Garantir que o modo local utilize o LocalStack via env (`AWS_ENDPOINT_URL=http://localhost:4566`).
   - Criar script helper (ex.: `scripts/run_webhook_local.sh`) para evitar configuração manual repetitiva.

4. **Fluxo de validação local**
   - Documentar teste rápido:
     1. subir LocalStack,
     2. rodar webhook local,
     3. enviar payload Telegram de exemplo,
     4. confirmar persistência no DynamoDB local,
     5. confirmar publicação na SQS local.

5. **Padrão semelhante ao worker**
   - Reaproveitar abordagem do worker para:
     - scripts shell de bootstrap,
     - runbook claro,
     - comandos AWS CLI com `--endpoint-url http://localhost:4566`.

## Entregáveis

- [ ] `local-environment/docker-compose.yml`
- [ ] `local-environment/scripts/start.sh`
- [ ] `local-environment/scripts/create_resources.sh`
- [ ] `local-environment/scripts/send_test_message.sh`
- [ ] `local-environment/scripts/run_webhook_local.sh`
- [ ] `local-environment/README.md` com passo a passo completo
- [ ] `.env.local.example` para execução local

## Critérios de Aceite

- `./local-environment/scripts/start.sh` sobe LocalStack e cria recursos sem erro.
- `go run ./cmd/webhook` (ou script helper) sobe o webhook local sem configuração complexa.
- Enviar payload de `/start` para endpoint local retorna sucesso e persiste estado inicial do usuário.
- Uma ação que gere dispatch publica mensagem na `visa-reschedule-queue` local.
- Um dev novo consegue executar o fluxo local em até 5 minutos com o README.

## Dependências

- Nenhuma (task de entrada para acelerar desenvolvimento).

## Fora de Escopo

- Deploy real em AWS.
- Pipeline CI/CD.
- Emulação perfeita de todos os comportamentos da API Gateway/Lambda em produção.

## Exemplo de runbook (inspirado no worker)

```bash
# 1) subir ambiente local
cd local-environment
./scripts/start.sh

# 2) rodar lambda webhook local (modo dev)
./scripts/run_webhook_local.sh

# 3) enviar update do Telegram de exemplo
curl -X POST http://localhost:8080/webhook/telegram \
  -H 'Content-Type: application/json' \
  -d '{
    "update_id": 123,
    "message": {
      "chat": {"id": 999999},
      "text": "/start"
    }
  }'

# 4) validar recursos no localstack
aws --endpoint-url http://localhost:4566 sqs list-queues
aws --endpoint-url http://localhost:4566 dynamodb list-tables
```
