# Visa Reschedule for Brasil 🇧🇷 🇺🇸

A serverless application that monitors the [AIS USA Visa portal](https://ais.usvisa-info.com/pt-br/niv) and notifies Brazilian applicants via Telegram when an earlier appointment date becomes available.

---

## Features

- 🔔 **Automated monitoring** – checks for earlier dates 3× daily (08:00, 14:00, 20:00 UTC)
- 📱 **Telegram notifications** – instant alerts when a date earlier than your current appointment is found
- 🤖 **Telegram bot** – guided onboarding and status commands
- ☁️ **Fully serverless** – AWS Lambda + DynamoDB + SQS
- 🔒 **Credential safety** – passwords are never logged or exposed in responses
- 💳 **Payment stub** – extensible payment module ready for future monetisation

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Compute | AWS Lambda (Python 3.11) |
| Database | Amazon DynamoDB |
| Queue | Amazon SQS |
| Scheduler | Amazon EventBridge |
| Browser automation | Selenium + ChromeDriver |
| Notifications | Telegram Bot API |
| Local testing | Flask + python-telegram-bot |
| IaC | AWS SAM |
| CI/CD | GitHub Actions |

---

## Project Structure

```text
.github/workflows/deploy-lambda.yml   # CI/CD pipeline
app/
  lambda_functions/
    user_registration.py              # API Gateway handler – register user
    check_available_dates.py          # EventBridge handler – enqueue users
    send_notifications.py             # SQS handler – Selenium + Telegram
  database/
    models.py                         # User & Appointment dataclasses
    dynamodb_client.py                # DynamoDB CRUD operations
  utils/
    selenium_utils.py                 # AIS portal automation
    notification_utils.py             # Telegram messaging
    payment.py                        # Payment stub (future feature)
  main.py                             # Flask app for local testing
  bot.py                              # Telegram bot for local testing
  local_sqs_worker.py                 # Local SQS worker (polls queue and invokes send_notifications)
  enqueue_manual_check.py             # CLI to enqueue a manual SQS check for a user
  requirements.txt
  env.example
  lambda_handler.py                   # Unified Lambda entry point
infrastructure/
  template.yml                        # AWS SAM template
```

---

## Setup

### Prerequisites

- Python 3.11+
- [AWS CLI](https://aws.amazon.com/cli/) configured
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- [Docker](https://www.docker.com/) (for LocalStack or SAM local)
- A Telegram bot token ([@BotFather](https://t.me/BotFather))
- Google Chrome + ChromeDriver (for local Selenium runs)

### Local development with LocalStack

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-org/visa-reschedule.git
   cd visa-reschedule
   ```

2. **Install Python dependencies**

   ```bash
   pip install -r app/requirements.txt
   ```

3. **Start LocalStack + provision resources (recommended)**

   This repo includes a LocalStack bootstrap script that:

   - Starts LocalStack (DynamoDB + SQS) via Docker Compose
   - Creates the DynamoDB tables + SQS queue
   - Copies `local-environment/.env.local` to repo-root `.env`

   Run:

   ```bash
   cd local-environment
   ./start.sh
   ```

4. **Install / configure env vars**

   - Edit the repo-root `.env` created by the script and set `TELEGRAM_BOT_TOKEN`.
   - If you prefer manual config instead of the script:

     ```bash
     cp app/env.example .env
     # Edit .env with your values (LocalStack endpoints + queue URL)
     ```

5. **Run the Flask app (local API Gateway simulator)**

   ```bash
   python -m app.main
   ```

6. **Run the local SQS worker (process queue messages)**

   In another terminal:

   ```bash
   python -m app.local_sqs_worker
   ```

7. **Register a user (choose one)**

   - Telegram onboarding:

     ```bash
     python -m app.bot
     ```

     Then send `/start` to your bot and follow the prompts.

   - REST registration:
     Use `POST /register` (example below). REST registration enqueues an immediate SQS message.

8. **Manual test: enqueue a check via SQS (CLI)**

   This forces a date-check for one user and can notify the user when the search completes:

   ```bash
   python -m app.enqueue_manual_check --user-id <uuid> --notify-start
   # or:
   python -m app.enqueue_manual_check --telegram-id <telegram_id> --notify-start
   ```

   If you only want to enqueue without “finished” notification:

   ```bash
   python -m app.enqueue_manual_check --user-id <uuid> --no-notify-complete
   ```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AWS_REGION` | AWS region (default: `us-east-1`) |
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `DYNAMODB_USERS_TABLE` | DynamoDB users table name |
| `DYNAMODB_USERS_TELEGRAM_INDEX` | Users table GSI name for telegram lookups (default: `telegram_id-index`) |
| `DYNAMODB_APPOINTMENTS_TABLE` | DynamoDB appointments table name |
| `DYNAMODB_ENDPOINT_URL` | Override endpoint (LocalStack: `http://localhost:4566`) |
| `APPOINTMENT_QUEUE_URL` | SQS queue URL |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `FLASK_DEBUG` | Enable Flask debug mode (`true`/`false`) |
| `FLASK_PORT` | Flask port (default: `5000`) |
| `ENVIRONMENT` | Runtime environment (`dev` shows browser by default; other values run headless by default) |
| `SELENIUM_HEADLESS` | Optional override for browser mode (`true`/`false`) |
| `CHROMEDRIVER_PATH` | Optional path to ChromeDriver binary |

---

## API Endpoints (Flask / API Gateway)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/register` | Register a new user |
| `GET` | `/users` | List all active users |
| `POST` | `/check-dates` | Manually trigger date check for a user |

### Register user example

```bash
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "secret",
    "telegram_id": "123456789",
    "visa_type": "B1/B2",
    "appointment_date": "01/12/2025"
  }'
```

---

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome menu and quick guidance |
| `/register` | Begin registration flow |
| `/status` | Check current monitoring status |
| `/cancel` | Cancel notifications |
| `/help` | Show available commands |

---

## Data Schema Documentation

Detailed DynamoDB schema docs (Users, Appointments, and Users table GSI):

- `docs/database-schema.md`

---

## Deployment

The CI/CD pipeline (`deploy-lambda.yml`) deploys automatically on every push to `main`.

To deploy manually:

```bash
sam build --template-file infrastructure/template.yml

sam deploy \
  --template-file infrastructure/template.yml \
  --stack-name visa-reschedule-prod \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides Environment=prod \
  --region us-east-1
```

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_REGION` | AWS region |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (also stored in SSM Parameter Store) |

### SSM Parameter Store

The SAM template reads the Telegram bot token from SSM:

```bash
aws ssm put-parameter \
  --name /visa-reschedule/prod/telegram-bot-token \
  --value "your-bot-token" \
  --type SecureString
```

---

## License

MIT
