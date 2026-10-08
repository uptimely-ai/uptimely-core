#!/usr/bin/env bash
set -euo pipefail

if ! command -v poetry >/dev/null 2>&1; then
    echo "Error: Poetry is required. Install it before tagging a release." >&2
    exit 1
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

branch="$(git branch --show-current)"
if [[ "$branch" != "main" ]]; then
    echo "Error: release tags must be created from main (currently on '$branch')." >&2
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Error: working tree is not clean; commit or discard changes first." >&2
    exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
    echo "Error: expected a Git remote named 'origin'." >&2
    exit 1
fi

git fetch --no-tags origin main

if ! git show-ref --verify --quiet refs/remotes/origin/main; then
    echo "Error: could not find origin/main after fetching." >&2
    exit 1
fi

if [[ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]]; then
    echo "Error: local main is not at origin/main; update main before tagging." >&2
    exit 1
fi

version="$(poetry version -s)"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: expected a stable X.Y.Z package version, got '$version'." >&2
    exit 1
fi

tag="v$version"
if git show-ref --verify --quiet "refs/tags/$tag"; then
    echo "Error: tag '$tag' already exists locally." >&2
    exit 1
fi

remote_tag="$(git ls-remote --tags origin "refs/tags/$tag")"
if [[ -n "$remote_tag" ]]; then
    echo "Error: tag '$tag' already exists on origin." >&2
    exit 1
fi

printf "Create and push annotated release tag %s at %s? [y/N] " "$tag" "$(git rev-parse --short HEAD)"
read -r confirmation
if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
    echo "Aborted; no tag was created."
    exit 0
fi

git tag -a "$tag" -m "Release $tag"
git push origin "$tag"
echo "Pushed $tag. The GitHub Actions release workflow should now run."
