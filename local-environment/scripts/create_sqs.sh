#!/bin/sh
set -eu

AWS_REGION="${AWS_REGION:-us-east-1}"
SQS_QUEUE_NAME="${SQS_QUEUE_NAME:-visa-reschedule-appointments}"
SQS_DLQ_NAME="${SQS_DLQ_NAME:-visa-reschedule-appointments-dlq}"

info() { echo "[INFO]  $*" >&2; }

get_queue_url() {
    queue_name="$1"
    awslocal sqs get-queue-url \
        --queue-name "${queue_name}" \
        --region "${AWS_REGION}" \
        --query "QueueUrl" \
        --output text 2>/dev/null || true
}

ensure_queue() {
    queue_name="$1"
    attributes="$2"

    queue_url=$(get_queue_url "${queue_name}")
    if [ -n "${queue_url}" ] && [ "${queue_url}" != "None" ]; then
        info "SQS queue '${queue_name}' already exists; skipping creation."
        echo "${queue_url}"
        return
    fi

    info "Creating SQS queue '${queue_name}'..."
    awslocal sqs create-queue \
        --queue-name "${queue_name}" \
        --attributes "${attributes}" \
        --region "${AWS_REGION}" \
        --query "QueueUrl" \
        --output text
}

DLQ_URL=$(ensure_queue "${SQS_DLQ_NAME}" "MessageRetentionPeriod=1209600")

DLQ_ARN=$(awslocal sqs get-queue-attributes \
    --queue-url "${DLQ_URL}" \
    --attribute-names QueueArn \
    --region "${AWS_REGION}" \
    --query "Attributes.QueueArn" \
    --output text)

REDRIVE_POLICY="{\"deadLetterTargetArn\":\"${DLQ_ARN}\",\"maxReceiveCount\":\"3\"}"

QUEUE_URL=$(ensure_queue "${SQS_QUEUE_NAME}" "VisibilityTimeout=660,MessageRetentionPeriod=86400")

ATTRS_FILE="$(mktemp)"
trap 'rm -f "${ATTRS_FILE}"' EXIT
ESCAPED_REDRIVE_POLICY=$(printf '%s' "${REDRIVE_POLICY}" | sed 's/"/\\"/g')
printf '{"RedrivePolicy":"%s"}' "${ESCAPED_REDRIVE_POLICY}" > "${ATTRS_FILE}"

awslocal sqs set-queue-attributes \
    --queue-url "${QUEUE_URL}" \
    --attributes "file://${ATTRS_FILE}" \
    --region "${AWS_REGION}" >/dev/null

info "SQS provisioning finished."
echo "${QUEUE_URL}"
