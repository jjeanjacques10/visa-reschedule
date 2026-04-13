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

```
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

3. **Configure environment variables**

   ```bash
   cp app/env.example app/.env
   # Edit app/.env with your values
   ```

4. **Start LocalStack** (Docker required)

   ```bash
   docker run --rm -d -p 4566:4566 localstack/localstack
   ```

5. **Create DynamoDB tables locally**

   ```bash
    aws --endpoint-url=http://localhost:4566 dynamodb create-table \
      --table-name visa-reschedule-users \
      --attribute-definitions \
        AttributeName=user_id,AttributeType=S \
        AttributeName=telegram_id,AttributeType=S \
      --key-schema AttributeName=user_id,KeyType=HASH \
      --global-secondary-indexes \
        '[{"IndexName":"telegram_id-index","KeySchema":[{"AttributeName":"telegram_id","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}]' \
      --billing-mode PAY_PER_REQUEST

   aws --endpoint-url=http://localhost:4566 dynamodb create-table \
     --table-name visa-reschedule-appointments \
     --attribute-definitions AttributeName=appointment_id,AttributeType=S \
     --key-schema AttributeName=appointment_id,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST
   ```

6. **Create the SQS queue locally**

   ```bash
   aws --endpoint-url=http://localhost:4566 sqs create-queue \
     --queue-name visa-reschedule-appointments
   ```

7. **Run the Flask app**

   ```bash
   cd app
   python main.py
   ```

8. **Run the Telegram bot**

   ```bash
   cd app
   python bot.py
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
    "appointment_date": "2025-12-01"
  }'
```

---

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Begin registration flow |
| `/status` | Check current monitoring status |
| `/cancel` | Cancel notifications |

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
