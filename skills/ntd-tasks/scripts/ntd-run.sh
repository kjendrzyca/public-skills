#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

TOKEN=$(security find-generic-password -s "ntd-agent-token" -a "ntd" -w 2>/dev/null) || {
  echo "Error: No agent token found in macOS Keychain." >&2
  echo "Store one first with:" >&2
  echo "bash -lc 'read -rsp \"Paste NTD token: \" TOKEN && echo && security add-generic-password -s \"ntd-agent-token\" -a \"ntd\" -w \"\$TOKEN\" -U && unset TOKEN'" >&2
  exit 1
}

printf '%s' "$TOKEN" | node "$SCRIPT_DIR/ntd-client.mjs" "$@"
