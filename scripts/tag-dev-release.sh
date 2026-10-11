#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/tag-release-common.sh"

tag_release 'development' '^[0-9]+\.[0-9]+\.[0-9]+\.dev[0-9]+$' 'X.Y.Z.devN' 'Development release'
