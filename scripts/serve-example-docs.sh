#!/usr/bin/env bash
(
  set -euo pipefail

  repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
  cd -- "$repo_root"

  exec poetry run uptimely docs serve \
    --spec examples/pump_analytics/_generated/spec/spec.json \
    --project-root examples/pump_analytics \
    --directory examples/pump_analytics/_generated/docs \
    "$@"
)
