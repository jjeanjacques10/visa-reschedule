#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
set -a
source "$ROOT_DIR/.env.local"
set +a
go run "$ROOT_DIR/cmd/webhook"
