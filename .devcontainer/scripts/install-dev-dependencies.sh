#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

poetry install --with test,dev,docs --extras "mcp s3"
