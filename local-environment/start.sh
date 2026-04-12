#!/usr/bin/env bash
# =============================================================================
# start.sh — Bootstrap the local development environment for visa-reschedule
#
# What this script does:
#   1. Starts LocalStack via Docker Compose (if not already running)
#   2. Waits until LocalStack is healthy
#   3. Creates DynamoDB tables (Users, Appointments)
#   4. Creates the SQS queue (AppointmentQueue)
#   5. Copies .env.local → ../.env so the app picks it up automatically
#
# Prerequisites:
#   - Docker and Docker Compose installed
#   - AWS CLI installed (used to provision resources via LocalStack)
#
# Usage:
#   cd local-environment
#   chmod +x start.sh
#   ./start.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

LOCALSTACK_ENDPOINT="http://localhost:4566"
AWS_REGION="us-east-1"
# LocalStack uses a fixed dummy account; credentials can be anything non-empty.
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"
export AWS_DEFAULT_REGION="${AWS_REGION}"

USERS_TABLE="visa-reschedule-users"
APPOINTMENTS_TABLE="visa-reschedule-appointments"
SQS_QUEUE_NAME="visa-reschedule-appointments"
SQS_DLQ_NAME="visa-reschedule-appointments-dlq"

# Colours
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Dependency checks ─────────────────────────────────────────────────────────

check_dependency() {
    if ! command -v "$1" &>/dev/null; then
        error "'$1' is not installed or not on PATH."
        error "Please install it and re-run this script."
        exit 1
    fi
}

info "Checking dependencies..."
check_dependency docker
check_dependency aws

# ── Start LocalStack ──────────────────────────────────────────────────────────

info "Starting LocalStack..."
cd "${SCRIPT_DIR}"

if docker compose ps localstack 2>/dev/null | grep -q "running"; then
    info "LocalStack is already running."
else
    docker compose up -d localstack
fi

# ── Wait for LocalStack to be healthy ─────────────────────────────────────────

info "Waiting for LocalStack to be ready..."
MAX_RETRIES=30
RETRY_INTERVAL=3

for i in $(seq 1 "${MAX_RETRIES}"); do
    if curl -sf "${LOCALSTACK_ENDPOINT}/_localstack/health" \
            | grep -q '"dynamodb": "running"' 2>/dev/null; then
        info "LocalStack is ready."
        break
    fi
    if [ "${i}" -eq "${MAX_RETRIES}" ]; then
        error "LocalStack did not become healthy after $((MAX_RETRIES * RETRY_INTERVAL)) seconds."
        error "Check 'docker compose logs localstack' for details."
        exit 1
    fi
    warn "LocalStack not ready yet (attempt ${i}/${MAX_RETRIES}). Retrying in ${RETRY_INTERVAL}s..."
    sleep "${RETRY_INTERVAL}"
done

# ── Helper: create DynamoDB table (idempotent) ────────────────────────────────

create_dynamodb_table() {
    local table_name="$1"
    local pk_name="$2"

    if aws dynamodb describe-table \
            --table-name "${table_name}" \
            --endpoint-url "${LOCALSTACK_ENDPOINT}" \
            --region "${AWS_REGION}" \
            --output text &>/dev/null; then
        info "DynamoDB table '${table_name}' already exists – skipping."
        return
    fi

    info "Creating DynamoDB table '${table_name}'..."
    aws dynamodb create-table \
        --table-name "${table_name}" \
        --attribute-definitions AttributeName="${pk_name}",AttributeType=S \
        --key-schema AttributeName="${pk_name}",KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --endpoint-url "${LOCALSTACK_ENDPOINT}" \
        --region "${AWS_REGION}" \
        --output text > /dev/null
    info "Table '${table_name}' created."
}

# ── Helper: create SQS queue (idempotent) ─────────────────────────────────────

create_sqs_queue() {
    local queue_name="$1"
    local extra_args=("${@:2}")

    local existing
    existing=$(aws sqs get-queue-url \
        --queue-name "${queue_name}" \
        --endpoint-url "${LOCALSTACK_ENDPOINT}" \
        --region "${AWS_REGION}" \
        --output text 2>/dev/null || true)

    if [ -n "${existing}" ]; then
        info "SQS queue '${queue_name}' already exists – skipping."
        echo "${existing}"
        return
    fi

    info "Creating SQS queue '${queue_name}'..."
    local queue_url
    queue_url=$(aws sqs create-queue \
        --queue-name "${queue_name}" \
        --endpoint-url "${LOCALSTACK_ENDPOINT}" \
        --region "${AWS_REGION}" \
        "${extra_args[@]}" \
        --query "QueueUrl" \
        --output text)
    info "Queue '${queue_name}' created: ${queue_url}"
    echo "${queue_url}"
}

# ── Provision DynamoDB tables ─────────────────────────────────────────────────

create_dynamodb_table "${USERS_TABLE}"        "user_id"
create_dynamodb_table "${APPOINTMENTS_TABLE}" "appointment_id"

# ── Provision SQS queues ──────────────────────────────────────────────────────

DLQ_URL=$(create_sqs_queue "${SQS_DLQ_NAME}" \
    --attributes "MessageRetentionPeriod=1209600")

DLQ_ARN=$(aws sqs get-queue-attributes \
    --queue-url "${DLQ_URL}" \
    --attribute-names QueueArn \
    --endpoint-url "${LOCALSTACK_ENDPOINT}" \
    --region "${AWS_REGION}" \
    --query "Attributes.QueueArn" \
    --output text)

REDRIVE_POLICY="{\"deadLetterTargetArn\":\"${DLQ_ARN}\",\"maxReceiveCount\":\"3\"}"

QUEUE_URL=$(create_sqs_queue "${SQS_QUEUE_NAME}" \
    --attributes "VisibilityTimeout=660,MessageRetentionPeriod=86400,RedrivePolicy=${REDRIVE_POLICY}")

# ── Copy .env.local → ../.env ─────────────────────────────────────────────────

ENV_SRC="${SCRIPT_DIR}/.env.local"
ENV_DST="${REPO_ROOT}/.env"

if [ -f "${ENV_DST}" ]; then
    warn ".env already exists at ${ENV_DST} – not overwriting."
    warn "Delete it manually and re-run if you want to reset to defaults."
else
    cp "${ENV_SRC}" "${ENV_DST}"
    # Patch the queue URL with the actual LocalStack value.
    # Use a temp file for portability (avoids 'sed -i' GNU vs BSD differences).
    TMP_ENV="${ENV_DST}.tmp"
    sed "s|^APPOINTMENT_QUEUE_URL=.*|APPOINTMENT_QUEUE_URL=${QUEUE_URL}|" \
        "${ENV_DST}" > "${TMP_ENV}" && mv "${TMP_ENV}" "${ENV_DST}"
    info "Created ${ENV_DST} from .env.local."
    warn "Remember to set TELEGRAM_BOT_TOKEN in ${ENV_DST} before running the bot."
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
info "Local environment is ready."
info "  DynamoDB Users table    : ${USERS_TABLE}"
info "  DynamoDB Appointments   : ${APPOINTMENTS_TABLE}"
info "  SQS queue URL           : ${QUEUE_URL}"
info "  LocalStack endpoint     : ${LOCALSTACK_ENDPOINT}"
echo ""
info "To start the Flask app:"
echo "    cd ${REPO_ROOT} && python -m app.main"
echo ""
info "To start the Telegram bot:"
echo "    cd ${REPO_ROOT} && python -m app.bot"
echo ""
info "To stop LocalStack:"
echo "    cd ${SCRIPT_DIR} && docker compose down"
