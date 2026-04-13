#!/bin/sh
set -eu

AWS_REGION="${AWS_REGION:-us-east-1}"
USERS_TABLE="${USERS_TABLE:-visa-reschedule-users}"
APPOINTMENTS_TABLE="${APPOINTMENTS_TABLE:-visa-reschedule-appointments}"

info() { echo "[INFO]  $*" >&2; }
warn() { echo "[WARN]  $*" >&2; }

if awslocal dynamodb describe-table \
        --table-name "${USERS_TABLE}" \
        --region "${AWS_REGION}" \
        --output text &>/dev/null; then
    warn "DynamoDB table '${USERS_TABLE}' already exists; skipping."
else
    info "Creating DynamoDB table '${USERS_TABLE}' with GSI telegram_id-index..."
    awslocal dynamodb create-table \
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
        --output text &>/dev/null; then
    warn "DynamoDB table '${APPOINTMENTS_TABLE}' already exists; skipping."
else
    info "Creating DynamoDB table '${APPOINTMENTS_TABLE}'..."
    awslocal dynamodb create-table \
        --table-name "${APPOINTMENTS_TABLE}" \
        --attribute-definitions AttributeName=appointment_id,AttributeType=S \
        --key-schema AttributeName=appointment_id,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region "${AWS_REGION}" \
        --output text >/dev/null
fi

info "DynamoDB provisioning finished."
