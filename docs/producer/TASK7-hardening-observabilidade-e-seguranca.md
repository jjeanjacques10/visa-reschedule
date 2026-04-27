# TASK 7: Hardening, Observabilidade e Segurança

## Objetivo

Adicionar requisitos não-funcionais para operação segura e confiável do producer em produção.

## Escopo

1. Observabilidade:
   - métricas de mensagens recebidas/enviadas/erros
   - logs estruturados com correlação
   - alarmes básicos (CloudWatch) provisionados via Terraform
2. Segurança:
   - revisão de segredo de token Telegram
   - plano de criptografia de senha (futuro com KMS)
   - masking de dados sensíveis em logs
3. Confiabilidade:
   - retries controlados para chamadas Telegram/SQS
   - idempotência básica em comandos críticos
4. Documentação operacional:
   - runbook de incidentes
   - checklist de deploy

## Entregáveis

- [ ] documentação de observabilidade e alarmes
- [ ] ajustes de logging/masking
- [ ] políticas de retry/idempotência documentadas e implementadas
- [ ] runbook operacional
- [ ] recursos de alarmes/log groups versionados em `infrastructure/terraform/cloudwatch.tf`

## Critérios de Aceite

- Painel mínimo com métricas principais disponível.
- Alarmes para falha elevada de envio SQS/Telegram configurados.
- Não há exposição de senha/token em logs.

## Dependências

- TASK 4
- TASK 5
- TASK 6

## Fora de Escopo

- Features novas de produto (ex.: multi idioma, UI web).
