#!/usr/bin/env bash
# =============================================================================
# start.sh — Bootstrap the local development environment for visa-reschedule
#
# What this script does:
#   1. Starts LocalStack + DynamoDB Admin via Docker Compose
#   2. Waits until LocalStack is healthy
#   3. Runs provisioning scripts mounted in /etc/localstack/init/ready.d
#   4. Copies .env.local → ../.env so the app picks it up automatically
#
# Prerequisites:
#   - Docker and Docker Compose installed
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
LOCALSTACK_CONTAINER="visa-reschedule-localstack"

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

# ── Start services ────────────────────────────────────────────────────────────

info "Starting LocalStack and DynamoDB Admin..."
cd "${SCRIPT_DIR}"
docker compose up -d localstack dynamodb-admin

# ── Wait for LocalStack to be healthy ─────────────────────────────────────────

info "Waiting for LocalStack to be healthy..."
MAX_RETRIES=30
RETRY_INTERVAL=3

for i in $(seq 1 "${MAX_RETRIES}"); do
    HEALTH_STATUS=$(docker inspect \
        --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' \
        "${LOCALSTACK_CONTAINER}" 2>/dev/null || echo "unknown")

    if [ "${HEALTH_STATUS}" = "healthy" ]; then
        info "LocalStack is ready."
        break
    fi

    if [ "${i}" -eq "${MAX_RETRIES}" ]; then
        error "LocalStack did not become healthy after $((MAX_RETRIES * RETRY_INTERVAL)) seconds."
        error "Check 'docker compose logs localstack' for details."
        exit 1
    fi

    warn "LocalStack status is '${HEALTH_STATUS}' (attempt ${i}/${MAX_RETRIES}). Retrying in ${RETRY_INTERVAL}s..."
    sleep "${RETRY_INTERVAL}"
done

# ── Provision resources via LocalStack init scripts ──────────────────────────

info "Provisioning resources inside LocalStack container..."
docker exec "${LOCALSTACK_CONTAINER}" sh /etc/localstack/init/ready.d/create_table.sh
docker exec "${LOCALSTACK_CONTAINER}" sh /etc/localstack/init/ready.d/create_sqs.sh

QUEUE_URL="${LOCALSTACK_ENDPOINT}/000000000000/${SQS_QUEUE_NAME}"

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
