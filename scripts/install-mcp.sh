#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

poetry config virtualenvs.in-project true --local
poetry install --extras "mcp"
poetry run uptimely analytics export \
  --module examples.pump_analytics.config.analytics.analytics \
  --output examples/pump_analytics/_generated/spec/spec.json
