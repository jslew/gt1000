#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

swift build --quiet --package-path GT1000AppPackage --product GT1000PatchDump >&2
exec GT1000AppPackage/.build/debug/GT1000PatchDump "$@"
