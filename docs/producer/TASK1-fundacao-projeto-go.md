# TASK 1: Fundação do Projeto Go (Producer)

## Objetivo

Criar a base do novo repositório `telegram-bot-producer` em Go, com estrutura de pastas, configuração de ambiente e bootstrap padrão para execução em AWS Lambda.

## Escopo

1. Criar estrutura inicial de diretórios conforme a SPEC:
   - `cmd/webhook`
   - `cmd/scheduler`
   - `internal/{app,domain,contracts,services,integrations,config,logger}`
   - `infrastructure/terraform`
2. Inicializar `go.mod` e organizar dependências base.
3. Criar carregamento de variáveis de ambiente com validação.
4. Criar logger estruturado JSON com correlação por request.
5. Definir skeleton de entrypoints para `webhook` e `scheduler`.

## Entregáveis

- [ ] Estrutura de diretórios criada (incluindo `infrastructure/terraform`).
- [ ] `go.mod` e `go.sum` inicializados.
- [ ] `internal/config/env.go` com leitura/validação de env.
- [ ] `internal/logger/logger.go` com logs JSON.
- [ ] `cmd/webhook/main.go` e `cmd/scheduler/main.go` compilando.
- [ ] `README.md` com instruções de build local.

## Critérios de Aceite

- `go test ./...` executa sem erro com skeleton mínimo.
- `go build ./cmd/webhook` e `go build ./cmd/scheduler` executam com sucesso.
- Falta de variáveis obrigatórias gera erro explícito.

## Dependências

- TASK 0 (ambiente local) recomendada para acelerar desenvolvimento e testes locais desde o início.

## Fora de Escopo

- Lógica de Telegram, DynamoDB, SQS e EventBridge.
