#!/usr/bin/env bash
(
  set -euo pipefail

  repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
  cd -- "$repo_root"

  exec poetry run uptimely explorer serve \
    --analytics examples/pump_analytics/_generated/analytics/analytics.json \
    --project-root examples/pump_analytics \
    --directory examples/pump_analytics/_generated/explorer \
    "$@"
)
