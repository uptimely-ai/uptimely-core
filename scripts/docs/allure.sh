#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd -- "$repo_root"

poetry run pytest \
  --alluredir=allure-results \
  --clean-alluredir \
  "$@"

npx --yes allure@3.33.0 generate allure-results \
  --clean \
  --output allure-report \
  --name "Uptimely Core Tests"

exec npx --yes allure@3.33.0 open allure-report
