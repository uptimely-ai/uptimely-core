#!/usr/bin/env bash
set -euo pipefail

apt-get update
apt-get install -y \
    build-essential \
    libssl-dev \
    pkg-config \
    ruby \
    ruby-bundler \
    ruby-dev
rm -rf /var/lib/apt/lists/*
