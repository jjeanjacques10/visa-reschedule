#!/bin/sh
set -eu

AWS_REGION="${AWS_REGION:-us-east-1}"
SQS_QUEUE_NAME="${SQS_QUEUE_NAME:-visa-reschedule-appointments}"
SQS_DLQ_NAME="${SQS_DLQ_NAME:-visa-reschedule-appointments-dlq}"

info() { echo "[INFO]  $*" >&2; }

create_sqs_queue() {
    queue_name="$1"
    attributes="${2:-}"

    existing=$(awslocal sqs get-queue-url \
        --queue-name "${queue_name}" \
        --region "${AWS_REGION}" \
        --query "QueueUrl" \
        --output text 2>/dev/null || true)

    if [ -n "${existing}" ] && [ "${existing}" != "None" ]; then
        info "SQS queue '${queue_name}' already exists; skipping."
        echo "${existing}"
        return
    fi

    info "Creating SQS queue '${queue_name}'..."

    if [ -n "${attributes}" ]; then
        awslocal sqs create-queue \
            --queue-name "${queue_name}" \
            --attributes "${attributes}" \
            --region "${AWS_REGION}" \
            --query "QueueUrl" \
            --output text
    else
        awslocal sqs create-queue \
            --queue-name "${queue_name}" \
            --region "${AWS_REGION}" \
            --query "QueueUrl" \
            --output text
    fi
}

DLQ_URL=$(create_sqs_queue "${SQS_DLQ_NAME}" "MessageRetentionPeriod=1209600")

DLQ_ARN=$(awslocal sqs get-queue-attributes \
    --queue-url "${DLQ_URL}" \
    --attribute-names QueueArn \
    --region "${AWS_REGION}" \
    --query "Attributes.QueueArn" \
    --output text)

REDRIVE_POLICY="{\"deadLetterTargetArn\":\"${DLQ_ARN}\",\"maxReceiveCount\":\"3\"}"

QUEUE_URL=$(create_sqs_queue "${SQS_QUEUE_NAME}" "VisibilityTimeout=660,MessageRetentionPeriod=86400,RedrivePolicy=${REDRIVE_POLICY}")

info "SQS provisioning finished."
echo "${QUEUE_URL}"
