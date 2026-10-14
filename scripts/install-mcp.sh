#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

poetry config virtualenvs.in-project true --local
poetry install --extras "mcp"
poetry run python -m examples.example_1.run_export_spec
