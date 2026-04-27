#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR/local-environment"
docker compose up -d
sleep 3
"$ROOT_DIR/local-environment/scripts/create_resources.sh"
echo "LocalStack pronto."
