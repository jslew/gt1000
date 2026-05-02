#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== Package tests =="
xcodebuildmcp swift-package test --package-path GT1000AppPackage

echo "== macOS UI smoke test =="
xcodebuildmcp macos test \
  --workspace-path GT1000App.xcworkspace \
  --scheme GT1000App \
  --configuration Debug

echo "== Build and run app =="
xcodebuildmcp macos build-and-run \
  --workspace-path GT1000App.xcworkspace \
  --scheme GT1000App \
  --configuration Debug \
  --arch arm64
