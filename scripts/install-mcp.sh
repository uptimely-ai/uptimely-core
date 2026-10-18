#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

poetry config virtualenvs.in-project true --local
poetry install --extras "mcp"
poetry run uptimely project build \
  --entrypoint examples.pump_analytics.config.spec.spec:python_spec \
  --project-root examples/pump_analytics
