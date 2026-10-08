#!/usr/bin/env bash
set -e

poetry install --with test,dev --extras "mcp s3"
poetry run python -m examples.example_1.run_export_spec
poetry run pre-commit install

(
    cd docs
    bundle config set --local path vendor/bundle
    bundle install
)
