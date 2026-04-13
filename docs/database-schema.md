# Database Schema

## Users Table (`visa-reschedule-users-{env}`)

### Primary Key
- `user_id` (String, HASH)

### Global Secondary Indexes
- `telegram_id-index`
  - Partition key: `telegram_id` (String)
  - Projection: `ALL`
  - Purpose: efficient retrieval of a user by Telegram ID without a table scan

### Attributes
- `user_id` (String)
- `telegram_id` (String)
- `visa_type` (String)
- `appointment_date` (String)
- `email` (String)
- `password` (String, sensitive)
- `created_at` (String, ISO 8601)
- `updated_at` (String, ISO 8601)
- `notification_count` (Number)
- `status` (String: `pending` | `notified` | `rescheduled` | `cancelled`)
- `last_notified_date` (String, optional)
- `preferred_dates` (List<String>, optional)
- `payment_status` (String, optional)

## Appointments Table (`visa-reschedule-appointments-{env}`)

### Primary Key
- `appointment_id` (String, HASH)

### Attributes
- `appointment_id` (String)
- `visa_type` (String)
- `available_dates` (List<String>)
- `last_checked` (String, ISO 8601)

