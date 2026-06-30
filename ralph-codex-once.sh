#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export RALPH_AGENT=codex
exec "$SCRIPT_DIR/ralph-once.sh"
