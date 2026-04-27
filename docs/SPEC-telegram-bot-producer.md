# SPEC - Telegram Bot Producer

## Objetivo

Esta especificação define um **novo repositório**, separado do worker atual (`visa-reschedule-worker`), para uma aplicação serverless em Go responsável por:

- Receber mensagens do Telegram via webhook
- Gerenciar onboarding e configuração do usuário
- Persistir estado/configuração do usuário
- Publicar mensagens na fila SQS `visa-reschedule-queue` (consumida pelo worker atual)
- Receber eventos periódicos via EventBridge para reenviar consultas de usuários ativos

> Observação: este repositório atual continua sendo apenas o consumidor da fila. O produtor (Telegram Bot Producer) será implementado em outro repositório.

---

## Tecnologias

- Go 1.24+
- AWS Lambda
- API Gateway
- Amazon SQS
- Amazon EventBridge
- DynamoDB
- Telegram Bot API
- Terraform (Infraestrutura como Código)

---

## Arquitetura

### Componentes

- **API Gateway (Webhook Endpoint)**
  - Endpoint HTTP público para receber updates do Telegram.
  - Encaminha o payload para a Lambda de webhook.

- **LambdaWebhookHandler**
  - Processa updates recebidos do Telegram.
  - Executa state machine de onboarding e comandos.
  - Persiste mudanças de estado no DynamoDB.
  - Publica mensagens na `visa-reschedule-queue` quando necessário.

- **LambdaScheduledDispatcher**
  - Executada periodicamente via EventBridge.
  - Busca usuários ativos no DynamoDB.
  - Reenvia requests para a SQS para nova tentativa de reagendamento.

- **DynamoDB (configuração e estado do usuário)**
  - Armazena dados de onboarding, estado da conversa e status do monitoramento.

- **SQS Producer**
  - Componente lógico utilizado por ambas as Lambdas para publicar mensagens na fila.

- **EventBridge Rule**
  - Dispara eventos periódicos (ex.: a cada X minutos) para acionar a `LambdaScheduledDispatcher`.

### Diagrama textual

```text
Telegram -> API Gateway -> LambdaWebhookHandler -> DynamoDB / SQS

EventBridge -> LambdaScheduledDispatcher -> DynamoDB -> SQS
```

---

## Estrutura de Pastas

Estrutura sugerida para o **novo repositório em Go**, seguindo organização semelhante ao projeto atual (separação por domínio, contrato e infraestrutura):

```text
telegram-bot-producer/
  cmd/
    webhook/
      main.go
    scheduler/
      main.go

  internal/
    app/
      webhook_handler.go
      scheduled_dispatcher.go

    domain/
      user.go
      onboarding_state.go
      commands.go
      validation.go

    contracts/
      telegram_update.go
      sqs_message.go
      eventbridge_event.go

    services/
      onboarding_service.go
      command_service.go
      dispatch_service.go

    integrations/
      telegram_client.go
      sqs_producer.go
      dynamodb_repository.go

    config/
      env.go

    logger/
      logger.go

  docs/
    SPEC-telegram-bot-producer.md

  infrastructure/
    terraform/
      main.tf
      variables.tf
      outputs.tf
      api_gateway.tf
      lambda.tf
      dynamodb.tf
      sqs.tf
      eventbridge.tf
      iam.tf
      cloudwatch.tf

  go.mod
  go.sum
  README.md
```

---

## Fluxo de Onboarding do Usuário

O onboarding deve operar como uma **state machine por usuário/chat_id**, garantindo continuidade da conversa entre mensagens.

### Passo a passo

1. Usuário envia `/start` (ou primeira interação, como “Oi”, “Olá” etc.).
2. Bot envia mensagem de boas-vindas e explica o objetivo.
3. Bot solicita email do portal AIS.
4. Bot solicita senha (com aviso de armazenamento criptografado no futuro).
5. Bot solicita data atual da entrevista.
6. Bot solicita data desejada para antecipação.
7. Bot solicita cidade/consulado (oferecer lista de opções válidas).
8. Bot salva configuração no DynamoDB (nova tabela de usuários).
9. Bot envia resumo da configuração coletada.
10. Bot pergunta se deseja iniciar monitoramento.
11. Se confirmado, publica a primeira mensagem na `visa-reschedule-queue`.

### Exemplo de estados

```text
WAITING_EMAIL
WAITING_PASSWORD
WAITING_CURRENT_DATE
WAITING_DESIRED_DATE
WAITING_CITY
WAITING_CONFIRMATION
ACTIVE
```

### Regras da state machine

- Cada `chat_id` possui um único estado atual.
- Mensagens fora de contexto devem receber resposta orientando próximo passo esperado.
- Estado precisa ser persistido após cada transição.
- Em caso de erro de validação, permanece no mesmo estado e solicita novo input.

---

## Fluxo de Consulta do Usuário

Quando o usuário já está configurado, o bot deve interpretar comandos de operação:

- Consultar status
- Alterar data desejada
- Pausar monitoramento
- Retomar monitoramento

### Exemplo

```text
Usuário -> /status
Bot -> "Sua entrevista atual é 20/09/2026. Estamos procurando datas até 15/07/2026."
```

### Comportamentos esperados

- `/status`: retorna configuração atual e status (`ativo`/`pausado`).
- `/alterar_data`: inicia subfluxo para capturar nova data desejada e validar regra de negócio.
- `/pausar`: define `monitoring_enabled = false`.
- `/retomar`: define `monitoring_enabled = true` e pode publicar nova mensagem inicial na SQS.

---

## Exemplo de comunicação com o Telegram

Para envio de mensagens ao Telegram, usar a API de Bot:

- https://core.telegram.org/method/messages.sendMessage

Exemplo em Go (adaptado):

```go
package telegram

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

type APIResponse struct {
	OK          bool   `json:"ok"`
	ErrorCode   int    `json:"error_code,omitempty"`
	Description string `json:"description,omitempty"`
}

func CallTelegramAPI(botToken, method string, payload any) (*APIResponse, error) {
	url := fmt.Sprintf("https://api.telegram.org/bot%s/%s", botToken, method)
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	resp, err := http.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var result APIResponse
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, err
	}

	return &result, nil
}
```

---

## Entradas da Aplicação

### Entrada 1 - Webhook do Telegram

Payload recebido pelo API Gateway e entregue para a `LambdaWebhookHandler`.

Exemplo simplificado:

```json
{
  "update_id": 123,
  "message": {
    "chat": {
      "id": 999999
    },
    "text": "/start"
  }
}
```

### Entrada 2 - EventBridge

Evento periódico para reprocessar usuários ativos.

Exemplo:

```json
{
  "source": "visa-rescheduler.scheduler",
  "detail-type": "dispatch-active-users"
}
```

Ao receber esse evento, a Lambda deve:

- Buscar usuários ativos no DynamoDB
- Montar payload de cada usuário
- Reenviar mensagens para a SQS

---

## Mensagens Publicadas na SQS

Fila de destino: `visa-reschedule-queue`.

Exemplo de payload:

```json
{
  "request_id": "uuid",
  "client_id": "telegram-999999",
  "telegram_chat_id": "999999",
  "portal_username": "user@email.com",
  "portal_password": "encrypted-password",
  "current_appointment_date": "2026-09-20",
  "desired_appointment_date": "2026-07-15",
  "city": "Sao Paulo"
}
```

Campos mínimos recomendados:

- `request_id`
- `client_id`
- `telegram_chat_id`
- `portal_username`
- `portal_password`
- `current_appointment_date`
- `desired_appointment_date`
- `city`

---

## Lista de Comandos do Bot

| Comando         | Descrição                                    |
| --------------- | -------------------------------------------- |
| /iniciar        | Inicia onboarding                            |
| /ajuda          | Lista comandos                               |
| /status         | Mostra configuração atual                    |
| /pausar         | Pausa monitoramento                          |
| /retomar        | Retoma monitoramento                         |
| /alterar_data   | Altera data desejada                         |
| /alterar_cidade | Altera consulado/cidade                      |
| /parar          | Remove configuração e encerra monitoramento  |

Comandos futuros:

- `/alterar_email`
- `/alterar_senha`

---

## Fluxo de Mensagens do Bot

Exemplo de conversa completa:

```text
Usuário: /iniciar
Bot: Olá! Vou te ajudar a monitorar vagas do visto americano.

Bot: Qual é o email usado no portal AIS?
Usuário: user@email.com

Bot: Qual é sua senha?
Usuário: ********

Bot: Qual é a data atual da sua entrevista? (AAAA-MM-DD)
Usuário: 2026-09-20

Bot: Qual é a data desejada? (AAAA-MM-DD)
Usuário: 2026-07-15

Bot: Em qual cidade está sua entrevista? (São Paulo, Rio de Janeiro, Brasília, Recife)
Usuário: São Paulo

Bot: Resumo da sua configuração:
- Email: user@email.com
- Data atual: 2026-09-20
- Data desejada: 2026-07-15
- Cidade: São Paulo
Deseja iniciar o monitoramento agora? (sim/não)

Usuário: sim
Bot: Perfeito! Monitoramento iniciado. Vou te avisar quando encontrarmos uma data melhor.
```

---

## Regras de Negócio

- Apenas um monitoramento ativo por `chat_id`
- Datas devem ser válidas (formato e calendário)
- `desired_date` deve ser anterior à `current_date`
- Senha deve ser armazenada criptografada (futuro com KMS; inicialmente sem criptografia)
- Usuário pode pausar e retomar monitoramento
- Usuários pausados não devem ser enviados pela rotina do EventBridge

---

## DynamoDB

Tabela sugerida:

```text
Table: visa-rescheduler-users
PK: id (UUID)
```

Campos:

- `id` (UUID)
- `chat_id`
- `state`
- `monitoring_enabled`
- `portal_username`
- `encrypted_password`
- `current_appointment_date`
- `desired_appointment_date`
- `city`
- `updated_at`

### GSI sugerida para consulta por chat_id

```text
GSI: telegram-index
PK: chat_id
```

### GSI sugerida para consulta por email

```text
GSI: email-index
PK: portal_username
```

---

## Infraestrutura (Terraform)

A infraestrutura do producer deve ser definida em **Terraform**, seguindo o mesmo direcionamento do worker.

### Escopo mínimo esperado em `infrastructure/terraform`

- `api_gateway.tf`
  - API Gateway HTTP para webhook do Telegram.
  - Integração com `LambdaWebhookHandler`.
- `lambda.tf`
  - Definição das Lambdas `webhook` e `scheduler`.
  - Runtime Go, timeout, memória, variáveis de ambiente e permissões.
- `dynamodb.tf`
  - Tabela `visa-rescheduler-users`.
  - GSIs `telegram-index` e `email-index`.
- `sqs.tf`
  - Referência à fila `visa-reschedule-queue` (ou data source, caso criada em stack externa).
- `eventbridge.tf`
  - Rule para disparo periódico de `dispatch-active-users`.
  - Target para `LambdaScheduledDispatcher`.
- `iam.tf`
  - Policies mínimas para acesso a DynamoDB, SQS, CloudWatch e invocação necessária.
- `cloudwatch.tf`
  - Log groups, retenção e alarmes mínimos.
- `variables.tf`, `main.tf`, `outputs.tf`
  - Variáveis, composição e outputs essenciais (ARNs, URLs, nomes).

### Observações de integração

- Caso a `visa-reschedule-queue` pertença ao repositório do worker, utilizar estratégia de integração entre stacks (ex.: `terraform_remote_state`, data source, ou variável injetada por ambiente).
- O deploy deve ser reproduzível por ambiente (`dev`, `staging`, `prod`) com arquivos `*.tfvars` e pipeline.

---

## Ambiente Local (DX para Lambda)

Para facilitar desenvolvimento (com baixa fricção), o projeto deve oferecer execução local simples:

- Subida de dependências AWS via LocalStack (`SQS`, `DynamoDB`, `EventBridge` opcional).
- Bootstrap automatizado de recursos com scripts shell.
- Execução da Lambda webhook em modo local com comando único (ex.: `go run ./cmd/webhook` ou script helper).
- Endpoint HTTP local para receber payload de webhook Telegram durante desenvolvimento.

Estrutura sugerida:

```text
local-environment/
  docker-compose.yml
  scripts/
    start.sh
    create_resources.sh
    run_webhook_local.sh
    send_test_message.sh
  README.md
```

Objetivo de experiência local:

- Um novo desenvolvedor deve conseguir subir LocalStack + rodar webhook local + enviar payload de teste em poucos minutos, sem configuração extensa.

---

## Variáveis de Ambiente

```text
TELEGRAM_BOT_TOKEN=
SQS_QUEUE_URL=
DYNAMODB_TABLE=
AES_SECRET_KEY=
```

---

## Fora de Escopo

- UI web
- Multi idioma
- Suporte a múltiplos usuários por chat
- Integração com outros mensageiros
- Persistência de histórico de mensagens
