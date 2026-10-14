#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

poetry run pre-commit install --hook-type pre-commit --hook-type pre-push
