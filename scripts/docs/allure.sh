#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd -- "$repo_root"

poetry run pytest \
  --alluredir=allure-results \
  --clean-alluredir \
  "$@"

rm -rf -- allure-report

npx --yes allure@3.33.0 awesome allure-results \
  --output allure-report \
  --name "Uptimely Core Tests" \
  --theme dark \
  --hide-labels host \
  --hide-labels thread \
  --hide-labels framework \
  --hide-labels language

exec npx --yes allure@3.33.0 open allure-report
