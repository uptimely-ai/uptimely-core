#!/usr/bin/env bash
(
  set -euo pipefail

  repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
  cd -- "$repo_root"

  if read -r -p "Build project files before serving? [y/N] " build_reply &&
    [[ "$build_reply" =~ ^[Yy]([Ee][Ss])?$ ]]; then
    poetry run uptimely build \
      --project-root example
  fi

  exec poetry run uptimely explore \
    --project-root example \
    "$@"
)
