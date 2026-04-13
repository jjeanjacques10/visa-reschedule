# SPEC Task — Site para controle de agendamento

## 1) Objetivo

Criar uma interface web para o usuário controlar o agendamento (consultar, reagendar e cancelar) com suporte de notificações por e-mail e opção de Telegram, mantendo a automação já existente via Lambdas.

## 2) Escopo funcional

### Funcionalidades do site
- Cadastro de usuário.
- Login de usuário usando senha do portal USA (AIS), conforme solicitado.
- Visualização de detalhes do agendamento atual.
- Solicitação de reagendamento.
- Solicitação de cancelamento.
- Consulta de histórico/status de tentativas de reagendamento.

### Notificações
- Enviar e-mail para o usuário em eventos importantes.
- Permitir opt-in de Telegram no perfil.
- Em reagendamento bem-sucedido, enviar e-mail com a nova data.

## 3) Fluxo principal esperado

1. Usuário cria conta no site com dados de acesso do portal e dados de contato.
2. Usuário escolhe canais de notificação (e-mail obrigatório, Telegram opcional).
3. Usuário cria/agenda uma rotina de verificação de reagendamento.
4. Lambda de verificação identifica data melhor.
5. Usuário aprova ação de reagendamento no site (ou política automática futura).
6. Lambda executa reagendamento.
7. Sistema atualiza dados do agendamento e envia notificação (e-mail + Telegram se habilitado).

## 4) Endpoints da API (MVP)

## Autenticação e usuário
- `POST /users`
  - Cria usuário.
  - Entrada: nome, e-mail, senha do portal, telegram_id (opcional), preferências.
- `POST /auth/login`
  - Login do usuário.
  - Entrada: e-mail + senha do portal.
  - Saída: token de sessão (JWT/cookie).
- `GET /users/me`
  - Retorna dados do usuário autenticado e preferências de notificação.
- `PATCH /users/me`
  - Atualiza preferências (Telegram on/off, e-mail, timezone, regras de notificação).

## Agendamento
- `POST /schedules`
  - Cria monitoramento de reagendamento para usuário.
  - Entrada: appointment_date atual, visa_type, regras (janela de datas, cidade/consulado).
- `GET /schedules/:id`
  - Consulta detalhes do monitoramento e agendamento atual.
- `GET /appointments/:id`
  - Consulta detalhes completos da entrevista vinculada.
- `POST /appointments/:id/reschedule`
  - Dispara tentativa de reagendamento.
  - Pode exigir confirmação do usuário no fluxo web.
- `POST /appointments/:id/cancel`
  - Cancela agendamento/monitoramento.

## Operação e status
- `GET /schedules/:id/status`
  - Status da fila/processamento (pending, processing, success, failed).
- `GET /notifications`
  - Histórico de notificações enviadas.

## 5) Alterações necessárias nas Lambdas

## 5.1 Lambda de cadastro/usuário
**Atual:** `UserRegistrationFunction` focada em registro básico.  
**Alterar para:**
- Validar payload do novo `POST /users`.
- Persistir preferências de notificação (e-mail e Telegram).
- Suportar atualização de perfil (`PATCH /users/me`).
- Nunca expor senha em resposta/log.

## 5.2 Nova Lambda de autenticação
**Nova:** `AuthFunction`
- Implementar `POST /auth/login`.
- Validar credenciais armazenadas.
- Emitir token de sessão (JWT/cookie seguro).
- Bloquear brute-force (rate limit + lock temporário).

## 5.3 Lambda de agendamento
**Nova ou expansão da atual API Lambda**
- `POST /schedules`, `GET /schedules/:id`, `GET /appointments/:id`.
- `POST /appointments/:id/reschedule`.
- `POST /appointments/:id/cancel`.
- Registrar auditoria de ações do usuário.

## 5.4 Lambda de verificação de datas
**Atual:** `CheckAvailableDatesFunction` coloca usuários na fila.  
**Alterar para:**
- Filtrar por schedules ativos (não cancelados).
- Respeitar configurações por usuário (timezone/janela de tentativa).
- Enfileirar contexto mínimo necessário (sem senha).

## 5.5 Lambda de notificação/reagendamento
**Atual:** `SendNotificationsFunction` envia Telegram ao achar datas.  
**Alterar para:**
- Suportar envio de e-mail além de Telegram.
- Em reagendamento concluído com sucesso, enviar e-mail com nova data.
- Atualizar appointment/schedule no banco após sucesso.
- Gravar histórico de notificação e resultado da execução.

## 5.6 Roteador unificado (`lambda_handler.py`)
- Adicionar roteamento para novos endpoints HTTP.
- Garantir distinção correta entre API Gateway, SQS e EventBridge.
- Padronizar respostas de erro para o frontend.

## 6) Alterações de dados (DynamoDB)

### Users
Adicionar/garantir campos:
- `email` (obrigatório)
- `telegram_id` (opcional)
- `notification_channels` (ex: `["email"]`, `["email","telegram"]`)
- `timezone`
- `status`

### Schedules
Criar/expandir entidade:
- `schedule_id`, `user_id`, `appointment_id`, `visa_type`
- `current_appointment_date`
- `status` (`active`, `paused`, `cancelled`, `rescheduled`)
- `created_at`, `updated_at`

### Appointments
Criar/expandir entidade:
- `appointment_id`, `user_id`, `consulate`, `asc`
- `current_date`, `last_successful_reschedule_date`
- `last_checked`, `last_result`

### Notifications/Audit (recomendado)
- Histórico de envio (`channel`, `event_type`, `delivered_at`, `status`).
- Auditoria de ações (`created_by`, `action`, `timestamp`, `metadata`).

## 7) Requisitos de segurança

- Não logar senha do portal em nenhuma Lambda.
- Criptografia em trânsito e em repouso (AWS managed keys).
- Token de sessão com expiração curta.
- Proteção contra brute-force e abuso de endpoints de login.
- Sanitização/validação de payload em todos os endpoints.

## 8) Critérios de aceite (MVP)

- Usuário consegue criar conta e fazer login no site.
- Usuário consegue visualizar detalhes do agendamento.
- Usuário consegue solicitar reagendamento e cancelamento.
- Sistema envia e-mail para eventos importantes.
- Se Telegram estiver habilitado, também envia Telegram.
- Em reagendamento bem-sucedido, e-mail com nova data é enviado.
- Endpoints listados estão disponíveis e integrados às Lambdas.

## 9) Fora do escopo inicial

- Cobrança/pagamentos.
- Regras avançadas de auto-reagendamento com múltiplas políticas.
- Painel administrativo completo.
