#!/usr/bin/env bash
set -euo pipefail

apt-get update
apt-get install -y \
    curl \
    git \
    python3-pip
rm -rf /var/lib/apt/lists/*

curl -fsSL https://install.python-poetry.org | python3 -
ln -s "${POETRY_HOME}/bin/poetry" /usr/local/bin/poetry

python -m pip install --upgrade pip setuptools
python -m pip install build twine
