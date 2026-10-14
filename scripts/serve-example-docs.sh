#!/usr/bin/env bash
(
  set -euo pipefail

  repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
  cd -- "$repo_root"

poetry run uptimely docs build \
  --spec examples/pump_analytics/_generated/spec/spec.json \
  --output examples/pump_analytics/_generated/docs

  exec poetry run uptimely docs serve \
    --directory examples/pump_analytics/_generated/docs \
    "$@"
)
