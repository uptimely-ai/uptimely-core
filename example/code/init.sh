#!/usr/bin/env bash

uptimely_init() {
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        (set -o pipefail; curl -LsSf https://astral.sh/uv/install.sh | sh) || return
    fi

    local project_dir
    project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || return
    uv sync --project "$project_dir"
}

uptimely_init
