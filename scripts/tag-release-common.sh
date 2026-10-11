tag_release() {
    local release_type="$1"
    local version_pattern="$2"
    local version_format="$3"
    local tag_message_prefix="$4"

    if ! command -v poetry >/dev/null 2>&1; then
        echo "Error: Poetry is required. Install it before tagging a $release_type release." >&2
        return 1
    fi

    local repo_root
    repo_root="$(git rev-parse --show-toplevel)"
    cd "$repo_root"

    local branch
    branch="$(git branch --show-current)"
    if [[ "$branch" != "main" ]]; then
        echo "Error: $release_type release tags must be created from main (currently on '$branch')." >&2
        return 1
    fi

    if [[ -n "$(git status --porcelain)" ]]; then
        echo "Error: working tree is not clean; commit or discard changes first." >&2
        return 1
    fi

    if ! git remote get-url origin >/dev/null 2>&1; then
        echo "Error: expected a Git remote named 'origin'." >&2
        return 1
    fi

    git fetch --no-tags origin main

    if ! git show-ref --verify --quiet refs/remotes/origin/main; then
        echo "Error: could not find origin/main after fetching." >&2
        return 1
    fi

    if [[ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]]; then
        echo "Error: local main is not at origin/main; update main before tagging." >&2
        return 1
    fi

    local version
    version="$(poetry version -s)"
    if [[ ! "$version" =~ $version_pattern ]]; then
        echo "Error: expected a $version_format package version, got '$version'." >&2
        return 1
    fi

    local tag="v$version"
    if git show-ref --verify --quiet "refs/tags/$tag"; then
        echo "Error: tag '$tag' already exists locally." >&2
        return 1
    fi

    local remote_tag
    remote_tag="$(git ls-remote --tags origin "refs/tags/$tag")"
    if [[ -n "$remote_tag" ]]; then
        echo "Error: tag '$tag' already exists on origin." >&2
        return 1
    fi

    printf "Create and push annotated %s tag %s at %s? [y/N] " \
        "$release_type release" "$tag" "$(git rev-parse --short HEAD)"
    local confirmation
    read -r confirmation
    if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
        echo "Aborted; no tag was created."
        return 0
    fi

    git tag -a "$tag" -m "$tag_message_prefix $tag"
    git push origin "$tag"
    echo "Pushed $tag. The GitHub Actions release workflow should now run."
}
