#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$ROOT/.playwright-browsers}"

if [[ ! -d node_modules/@playwright/test ]]; then
  npm install
fi

if [[ ! -d "$PLAYWRIGHT_BROWSERS_PATH" ]]; then
  npx playwright install chromium
fi

export GT1000_APP_URL="${GT1000_APP_URL:-http://127.0.0.1:38473}"
export GT1000_E2E_MODEL="${GT1000_E2E_MODEL:-gpt-5.5}"

exec npm run test:case1
