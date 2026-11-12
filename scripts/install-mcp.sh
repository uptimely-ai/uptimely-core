#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  printf '%s\n' \
    "Usage: scripts/install-mcp.sh" \
    "" \
    "Install the MCP extra in this checkout's Poetry environment and build the pump example." \
    "Run from any directory. Requires Poetry and the project's supported Python version." \
    "This script does not start a server or change your MCP client configuration."
  exit 0
fi
if [[ $# -ne 0 ]]; then
  printf '%s\n' "Unexpected arguments. Run scripts/install-mcp.sh --help." >&2
  exit 2
fi
if ! command -v poetry >/dev/null 2>&1; then
  printf '%s\n' \
    "Poetry is required for this repository setup script." \
    "For an installed package, use: python -m pip install 'uptimely-core[mcp]'" \
    "See docs/mcp/index.md for setup and client connection instructions." >&2
  exit 1
fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$repo_root"

# Respect the existing Poetry environment instead of forcing a .venv location.
poetry install --extras "mcp"
poetry run uptimely build examples/pump_analytics

printf '\n%s\n' \
  "MCP is installed and the pump example is built." \
  "VS Code: open this checkout, run MCP: List Servers, and start uptimely." \
  "Other clients: use Poetry with this checkout as the working directory:"
printf '  poetry run uptimely-mcp --project-root %q\n' "$repo_root/examples/pump_analytics"
printf '%s\n' \
  "Let the MCP client launch this command. No background server is needed." \
  "Connection examples and troubleshooting: docs/mcp/index.md"
