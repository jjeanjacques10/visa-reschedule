#!/bin/sh
set -eu

AWS_REGION="${AWS_REGION:-us-east-1}"
USERS_TABLE="${USERS_TABLE:-visa-reschedule-users}"
APPOINTMENTS_TABLE="${APPOINTMENTS_TABLE:-visa-reschedule-appointments}"

info() { echo "[INFO]  $*" >&2; }
warn() { echo "[WARN]  $*" >&2; }

create_dynamodb_table() {
    table_name="$1"
    pk_name="$2"

    if awslocal dynamodb describe-table \
            --table-name "${table_name}" \
            --region "${AWS_REGION}" \
            --output text &>/dev/null; then
        warn "DynamoDB table '${table_name}' already exists; skipping."
        return
    fi

    info "Creating DynamoDB table '${table_name}'..."
    awslocal dynamodb create-table \
        --table-name "${table_name}" \
        --attribute-definitions AttributeName="${pk_name}",AttributeType=S \
        --key-schema AttributeName="${pk_name}",KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region "${AWS_REGION}" \
        --output text >/dev/null
}

create_dynamodb_table "${USERS_TABLE}" "user_id"
create_dynamodb_table "${APPOINTMENTS_TABLE}" "appointment_id"

info "DynamoDB provisioning finished."
