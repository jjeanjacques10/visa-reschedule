#!/usr/bin/env bash
set -euo pipefail
curl -X POST http://localhost:8080/webhook/telegram \
  -H 'Content-Type: application/json' \
  -d '{"update_id":123,"message":{"chat":{"id":999999},"text":"/iniciar"}}'
