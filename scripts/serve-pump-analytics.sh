#!/usr/bin/env bash
(
  set -euo pipefail

  repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
  cd -- "$repo_root"

  if read -r -p "Build project files before serving? [y/N] " build_reply &&
    [[ "$build_reply" =~ ^[Yy]([Ee][Ss])?$ ]]; then
    poetry run uptimely project build \
      --project-root examples/pump_analytics
  fi

  exec poetry run uptimely explorer serve \
    --project-root examples/pump_analytics \
    "$@"
)
