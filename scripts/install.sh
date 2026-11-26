#!/bin/sh
set -eu

UPTIMELY_PACKAGE='uptimely-core@latest'

if [ "$#" -ne 0 ]; then
    printf '%s\n' "Usage: sh install.sh" >&2
    exit 2
fi

case "$(uname -s)" in
    Linux|Darwin) ;;
    *)
        printf '%s\n' "This installer supports Linux and macOS. On Windows, use WSL." >&2
        exit 1
        ;;
esac

: "${HOME:?HOME must be set}"
original_path=$PATH

if ! command -v uv >/dev/null 2>&1; then
    if [ -x "$HOME/.local/bin/uv" ]; then
        PATH="$HOME/.local/bin:$PATH"
        export PATH
    else
        if ! command -v curl >/dev/null 2>&1; then
            printf '%s\n' "curl is required to install uv. Install curl and try again." >&2
            exit 1
        fi
        installer=$(mktemp)
        trap 'rm -f "$installer"' 0
        trap 'exit 1' HUP INT TERM
        printf '%s\n' "Installing uv for the current user..."
        curl -fsSL https://astral.sh/uv/install.sh -o "$installer"
        UV_UNMANAGED_INSTALL= UV_NO_MODIFY_PATH=1 UV_INSTALL_DIR="$HOME/.local/bin" sh "$installer"
        PATH="$HOME/.local/bin:$PATH"
        export PATH
    fi
fi

printf '%s\n' "Installing Uptimely for the current user..."
uv tool install --python 3.13 "$UPTIMELY_PACKAGE"
tool_bin=$(uv tool dir --bin)
if [ ! -x "$tool_bin/uptimely" ]; then
    printf '%s\n' "Uptimely was not found in $tool_bin after installation." >&2
    exit 1
fi

printf '%s\n' "Configuring your shell PATH..."
uv_executable=$(command -v uv)
if ! PATH="$original_path" "$uv_executable" tool update-shell; then
    printf '%s\n' \
        "Uptimely was installed, but automatic PATH setup did not complete." \
        "Restart your terminal and check that 'uptimely --help' works." \
        "If it does not, add $tool_bin to your shell PATH." >&2
    exit 1
fi

printf '\n%s\n' \
    "Uptimely is installed in $tool_bin." \
    "Restart your terminal, then run: uptimely --help" \
    "Installed package: $UPTIMELY_PACKAGE."
