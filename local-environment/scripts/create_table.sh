#!/bin/sh
set -eu

AWS_REGION="${AWS_REGION:-us-east-1}"
USERS_TABLE="${USERS_TABLE:-visa-reschedule-users}"
APPOINTMENTS_TABLE="${APPOINTMENTS_TABLE:-visa-reschedule-appointments}"

info() { echo "[INFO]  $*" >&2; }
warn() { echo "[WARN]  $*" >&2; }

create_table() {
    table_name="$1"
    shift
    if output=$(awslocal dynamodb create-table "$@" 2>&1); then
        return 0
    fi

    if echo "${output}" | grep -q "ResourceInUseException"; then
        warn "DynamoDB table '${table_name}' already exists; skipping."
        return 0
    fi

    echo "${output}" >&2
    return 1
}

if awslocal dynamodb describe-table \
        --table-name "${USERS_TABLE}" \
        --region "${AWS_REGION}" \
    --output text >/dev/null 2>&1; then
    warn "DynamoDB table '${USERS_TABLE}' already exists; skipping."
else
    info "Creating DynamoDB table '${USERS_TABLE}' with GSI telegram_id-index..."
    create_table "${USERS_TABLE}" \
        --table-name "${USERS_TABLE}" \
        --attribute-definitions \
            AttributeName=user_id,AttributeType=S \
            AttributeName=telegram_id,AttributeType=S \
        --key-schema AttributeName=user_id,KeyType=HASH \
        --global-secondary-indexes \
            '[{"IndexName":"telegram_id-index","KeySchema":[{"AttributeName":"telegram_id","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}]' \
        --billing-mode PAY_PER_REQUEST \
        --region "${AWS_REGION}" \
        --output text >/dev/null
fi

if awslocal dynamodb describe-table \
        --table-name "${APPOINTMENTS_TABLE}" \
        --region "${AWS_REGION}" \
    --output text >/dev/null 2>&1; then
    warn "DynamoDB table '${APPOINTMENTS_TABLE}' already exists; skipping."
else
    info "Creating DynamoDB table '${APPOINTMENTS_TABLE}'..."
    create_table "${APPOINTMENTS_TABLE}" \
        --table-name "${APPOINTMENTS_TABLE}" \
        --attribute-definitions AttributeName=appointment_id,AttributeType=S \
        --key-schema AttributeName=appointment_id,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region "${AWS_REGION}" \
        --output text >/dev/null
fi

info "DynamoDB provisioning finished."
