#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

bash .devcontainer/scripts/install-dev-dependencies.sh
bash .devcontainer/scripts/install-git-hooks.sh
