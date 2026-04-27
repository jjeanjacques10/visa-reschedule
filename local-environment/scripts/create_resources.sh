#!/usr/bin/env bash
set -euo pipefail
EP="http://localhost:4566"
aws --endpoint-url "$EP" sqs create-queue --queue-name visa-reschedule-queue >/dev/null
aws --endpoint-url "$EP" dynamodb create-table \
  --table-name visa-rescheduler-users \
  --attribute-definitions AttributeName=id,AttributeType=S AttributeName=chat_id,AttributeType=N AttributeName=portal_username,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --global-secondary-indexes '[{"IndexName":"telegram-index","KeySchema":[{"AttributeName":"chat_id","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"},"ProvisionedThroughput":{"ReadCapacityUnits":5,"WriteCapacityUnits":5}},{"IndexName":"email-index","KeySchema":[{"AttributeName":"portal_username","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"},"ProvisionedThroughput":{"ReadCapacityUnits":5,"WriteCapacityUnits":5}}]' \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 >/dev/null || true
aws --endpoint-url "$EP" events put-rule --name dispatch-active-users-local --schedule-expression 'rate(10 minutes)' >/dev/null || true
echo "Recursos criados."
