# SPEC.md – Technical Specification: Visa Reschedule for Brasil

## 1. Architecture Overview

```
                    ┌──────────────────────────────────────┐
                    │            AWS Cloud                 │
                    │                                      │
  User ──Telegram──►│  Telegram Bot (local / Lambda)       │
                    │          │                           │
  User ──HTTP POST─►│  API Gateway  ──►  UserRegistration  │
                    │                       Lambda         │
                    │                          │           │
                    │                       DynamoDB       │
                    │                    (Users table)     │
                    │                                      │
                    │  EventBridge ──► CheckAvailableDates │
                    │  (3×/day)             Lambda         │
                    │                          │           │
                    │                         SQS          │
                    │                     (Appointment     │
                    │                       Queue)         │
                    │                          │           │
                    │               SendNotifications      │
                    │                    Lambda            │
                    │               (Selenium + Telegram)  │
                    └──────────────────────────────────────┘
```

### Flow Summary

1. Users register via Telegram bot or REST API.
2. Registration Lambda stores user credentials and appointment date in DynamoDB.
3. EventBridge triggers `CheckAvailableDates` 3× per day.
4. `CheckAvailableDates` scans DynamoDB for active users and enqueues each in SQS.
5. `SendNotifications` consumes SQS messages, logs into the AIS portal using Selenium, scrapes available dates, and sends Telegram notifications if earlier dates are found.

---

## 2. Database Schema

### Table: `visa-reschedule-users-{env}`

**Primary key:** `user_id` (String, UUID v4)
**GSI:** `telegram_id-index` (`telegram_id` as partition key)

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | String (PK) | UUID v4 – unique identifier |
| `telegram_id` | String | Telegram chat/user ID |
| `visa_type` | String | Visa category (e.g., B1/B2, F1) |
| `appointment_date` | String | Current appointment date (ISO or DD/MM/YYYY) |
| `email` | String | AIS portal login email |
| `password` | String | AIS portal login password (never logged) |
| `created_at` | String | ISO 8601 timestamp |
| `updated_at` | String | ISO 8601 timestamp |
| `notification_count` | Number | Total notifications sent |
| `status` | String | `pending` \| `notified` \| `rescheduled` \| `cancelled` |
| `last_notified_date` | String (optional) | ISO timestamp of last notification |
| `preferred_dates` | List\<String\> (optional) | User-specified preferred dates |
| `payment_status` | String (optional) | Stub for future payment feature |

#### Users table indexes

| Index name | Type | Partition key | Purpose |
|------------|------|---------------|---------|
| `telegram_id-index` | GSI | `telegram_id` | Fast lookup of users by Telegram ID for bot flows and notifications |

### Table: `visa-reschedule-appointments-{env}`

**Primary key:** `appointment_id` (String)

| Field | Type | Description |
|-------|------|-------------|
| `appointment_id` | String (PK) | Unique appointment snapshot ID |
| `visa_type` | String | Visa category |
| `available_dates` | List\<String\> | Dates available at time of check |
| `last_checked` | String | ISO 8601 timestamp of last scrape |

---

## 3. Lambda Functions

### 3.1 `UserRegistrationFunction`

- **Trigger:** API Gateway `POST /register`
- **Handler:** `app/lambda_handler.handler` → `user_registration.handler`
- **Input:** JSON body with `email`, `password`, `telegram_id`, `visa_type`, `appointment_date`
- **Output:** `200` with user data (password masked) | `400` validation error | `409` conflict | `500` server error
- **Side effects:** Creates a `User` record in DynamoDB

### 3.2 `CheckAvailableDatesFunction`

- **Trigger:** EventBridge cron `0 8,14,20 * * ? *` (08:00, 14:00, 20:00 UTC daily)
- **Handler:** `app/lambda_handler.handler` → `check_available_dates.handler`
- **Side effects:** Reads all active users from DynamoDB; enqueues each user (without password) into SQS

### 3.3 `SendNotificationsFunction`

- **Trigger:** SQS `AppointmentQueue` (batch size 1, `ReportBatchItemFailures` enabled)
- **Handler:** `app/lambda_handler.handler` → `send_notifications.handler`
- **Side effects:**
  - Fetches fresh user data from DynamoDB
  - Runs Selenium to check AIS portal for earlier dates
  - If found: sends Telegram notification, updates `last_notified_date`, increments `notification_count`, sets `status=notified`

---

## 4. Event Routing (`lambda_handler.py`)

The single Lambda entry point `app/lambda_handler.handler` distinguishes event sources by shape:

| Detection | Condition |
|-----------|-----------|
| API Gateway | `"httpMethod"` key present OR `"requestContext"` key present |
| SQS | `Records[0].eventSource == "aws:sqs"` |
| EventBridge | `event.source == "aws.events"` OR `"detail-type"` key present |

---

## 5. Selenium Automation Flow

All interactions use `WebDriverWait` (never `time.sleep`). Chrome runs in headless mode inside Lambda.

```
Step 1 ─ Login
  GET  https://ais.usvisa-info.com/pt-br/niv/users/sign_in
  ├── Fill #user_email
  ├── Fill #user_password
  ├── Check privacy policy checkbox
  └── Click "Acessar" button
       ↓ (wait for redirect to /groups/<group_id>)

Step 2 ─ Group page
  GET  https://ais.usvisa-info.com/pt-br/niv/groups/<group_id>
  └── Click "Continuar"
       ↓ (wait for /schedule/<id>/continue_actions)

Step 3 ─ Continue actions
  (current URL: /schedule/<id>/continue_actions)
  └── Click "Reagendar entrevista"
       ↓ (wait for /schedule/<id>/appointment)

Step 4 ─ Appointment page
  ├── Locate select#appointments_consulate_appointment_date
  ├── Locate select#appointments_asc_appointment_date
  ├── Collect all <option value="YYYY-MM-DD"> entries
  └── Return dates strictly earlier than user's current appointment_date
       (do NOT automatically click "Reagendar")
```

### Error handling in Selenium

| Scenario | Behaviour |
|----------|-----------|
| Invalid credentials | `TimeoutException` caught; `login()` returns `False` |
| CAPTCHA detected | Same as login failure (manual intervention required) |
| Element not found | `NoSuchElementException` caught and logged; returns empty list |
| General timeout | `TimeoutException` caught; logged as error; returns empty list |
| Unexpected exception | Logged with full traceback; `check_dates_for_user` returns `[]` |

---

## 6. Notification Format (Telegram)

Messages are sent in HTML parse mode:

```
🗓️ Datas disponíveis para reagendamento!

Seu agendamento atual: <current_date>

Datas disponíveis (anteriores ao seu agendamento atual):
  • YYYY-MM-DD
  • YYYY-MM-DD

Acesse o portal para reagendar sua entrevista.
```

---

## 7. Payment Stub (`app/utils/payment.py`)

Three stub functions exist for a future payment feature. All return mock responses and are no-ops:

| Function | Returns |
|----------|---------|
| `initiate_payment(user_id, amount, currency)` | `{"status": "pending", ...}` |
| `verify_payment(payment_id)` | `{"status": "unverified", ...}` |
| `update_user_payment_status(user_id, status)` | `False` |

When implemented, these will integrate with a payment gateway (e.g., Stripe, PagSeguro) and update `payment_status` on the `User` record.

---

## 8. API Endpoints

### POST /register

Registers a new user.

**Request body:**
```json
{
  "email": "user@example.com",
  "password": "portal_password",
  "telegram_id": "123456789",
  "visa_type": "B1/B2",
  "appointment_date": "2025-12-01",
  "preferred_dates": ["2025-10-15", "2025-11-01"]
}
```

**Response 200:**
```json
{
  "user": {
    "user_id": "uuid-v4",
    "telegram_id": "123456789",
    "visa_type": "B1/B2",
    "appointment_date": "2025-12-01",
    "email": "user@example.com",
    "status": "pending",
    "notification_count": 0,
    "created_at": "2025-01-01T00:00:00+00:00",
    "updated_at": "2025-01-01T00:00:00+00:00"
  }
}
```

### GET /health

Returns `{"status": "ok"}` with HTTP 200.

### GET /users

Returns a list of all active users (passwords omitted).

### POST /check-dates

Manually triggers a Selenium check for a given user.

**Request body:**
```json
{ "user_id": "uuid-v4" }
```

**Response 200:**
```json
{ "available_dates": ["2025-10-10", "2025-11-05"] }
```

---

## 9. Environment Variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `AWS_REGION` | All | AWS region |
| `DYNAMODB_USERS_TABLE` | Lambda, Flask | Users DynamoDB table name |
| `DYNAMODB_APPOINTMENTS_TABLE` | Lambda, Flask | Appointments DynamoDB table name |
| `DYNAMODB_ENDPOINT_URL` | Lambda, Flask | Custom endpoint (LocalStack) |
| `APPOINTMENT_QUEUE_URL` | CheckAvailableDates | SQS queue URL |
| `TELEGRAM_BOT_TOKEN` | SendNotifications, Bot | Telegram bot token |
| `FLASK_DEBUG` | Flask | Debug mode |
| `FLASK_PORT` | Flask | Listen port (default 5000) |
| `CHROMEDRIVER_PATH` | SeleniumUtils | Path to ChromeDriver binary |

---

## 10. Security Considerations

- Passwords are stored in DynamoDB and are required for portal automation; **they are never logged**.
- `User.to_safe_dict()` strips `password` before any API response or log entry.
- SQS messages never contain the user password (filtered in `check_available_dates`).
- Telegram bot attempts to delete messages containing passwords immediately after receipt.
- The Telegram bot token is stored in AWS SSM Parameter Store and injected at deploy time.
