# Contributing to Uptimely Core

Contributions are welcome via pull requests.

## Getting started

1. Fork the repository and clone your fork.
2. Open the repository in the included `.devcontainer/`, or, from the
   repository root, install locally:

   ```sh
   ./.devcontainer/scripts/install-dev-dependencies.sh
   ./.devcontainer/scripts/install-git-hooks.sh
   ```

Scripts under [`.devcontainer/scripts/`](.devcontainer/scripts/) set up the
development environment. The [Dockerfile](.devcontainer/Dockerfile) prepares
the image; [`post-create.sh`](.devcontainer/scripts/post-create.sh) prepares
the repository after the container is created.

Scripts under [`scripts/`](scripts/) are repository convenience actions to run
in an existing development environment. For example,
[`install-mcp.sh`](scripts/install-mcp.sh) installs the optional MCP extra and
prepares the example specification.

## Development process

1. Create a branch from `main`.
2. Make your change.
3. Commit and push your changes. The installed pre-commit hooks run checks,
   including the test suite when Python files are staged.
4. Open a pull request against `main`. Describe the motivation and link any
   related issue. CI must pass (lint, format, tests, coverage gate) before
   merge.

The CI quality job skips the pytest hook to avoid running tests twice. The
separate test job runs the suite with coverage; local commit hooks still run
tests when Python files are staged.

## Coding style

Follow the project's coding conventions in
[`.github/copilot-instructions.md`](.github/copilot-instructions.md).

### Python imports

Import modules and qualify their members. Use absolute imports from the owning
package across packages (`from uptimely.compiler import plan`), and single-dot
relative imports for siblings (`from . import errors`). Avoid multi-level
relative imports. Package `__init__.py` files may re-export individual public
symbols using relative imports.

### Changelog entries

For each pull request that changes behavior or adds something users can see,
add a concise entry under `## [Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md).
Use the relevant Keep a Changelog category, such as `Added`, `Changed`, or
`Fixed`. Describe the user impact rather than the implementation. Do not add a
version or date for an individual PR; release preparation moves these entries
under a version heading. Internal refactors and chores that do not affect users
do not normally need an entry.

## Branching and releases

### Branching strategy

The project uses trunk-based development. `main` is the only long-lived branch
and should always be releasable. Create short-lived branches from `main` and
merge them back through pull requests.

Keep `main` green by merging changes
that pass CI and splitting larger work into reviewable steps. Use an opt-in
code path to keep unfinished behavior hidden while integrating it through
short-lived branches.
Releases are tags on `main`.

> [!WARNING]
> There are no `develop` or `release/*` branches.

Name branches `<type>/<short-slug>`, where `<type>` is one of:

| Prefix | Use |
| --- | --- |
| `feature` | Add a user-facing feature or capability. |
| `fix` | Correct a bug or unintended behavior. |
| `docs` | Change documentation. |
| `refactor` | Restructure code without changing behavior. |
| `chore` | Perform maintenance or repository upkeep. |
| `test` | Add or update tests. |

`<short-slug>` is 2–5 lowercase, hyphenated words describing the change. For
example: `feature/multi-output-calculations` or
`fix/empty-spread-health-score`.

> [!WARNING]
> Do not use personal namespaces, version numbers, or dates in branch names.

Feature and fix branches usually result in changelog
entries; refactor and chore branches usually do not.

### Versioning policy

The project follows [Semantic Versioning](https://semver.org). Before `1.0.0`,
the API is unstable: minor releases may include breaking changes, and patch
releases may change behavior. From `1.0.0` onward, breaking changes will ship
only in major releases, with deprecations announced at least one minor release
in advance.

### Preparing and publishing releases

Prepare every release in a short-lived PR to `main`. Merge the PR only after review and CI pass. Once it is merged, create
and push the release tag from an up-to-date `main` checkout; the release script
checks the package version and repository state before creating the tag.

#### Stable release

1. Choose the next stable version according to the versioning policy.
2. Set `version` under `[project]` in [`pyproject.toml`](pyproject.toml) to that
   version, using the `X.Y.Z` format (for example, `0.2.0`).
3. In [`CHANGELOG.md`](CHANGELOG.md), replace `## [Unreleased]` with
   `## [<version>] - YYYY-MM-DD`, keeping its entries and categories. Add a
   fresh, empty `## [Unreleased]` section above the version heading.
4. Create a short-lived branch with a compliant name, such as
   `chore/prepare-release`. Run the normal checks, open a PR to `main`, and
   merge it after review and CI pass.
5. Update your local `main` and run the stable release script:

   ```sh
   git switch main
   git pull --ff-only
   ./scripts/tag/stable-release.sh
   ```

6. After the release, open a follow-up PR to set `pyproject.toml` to the next
   development version, such as `0.3.0.dev0`. Keep the fresh `Unreleased`
   changelog section in place.

#### Development release

1. Choose the development version to publish, using the PEP 440 format
   `X.Y.Z.devN` (for example, `0.3.0.dev1`). Increment `N` for every upload:
   PyPI does not allow replacing an already published version.
2. Set `version` under `[project]` in [`pyproject.toml`](pyproject.toml) to that
   development version. Leave [`CHANGELOG.md`](CHANGELOG.md) entries under
   `Unreleased`; do not create a dated heading for a development release.
3. Create a short-lived branch with a compliant name, such as
   `chore/prepare-development-release`. Run the normal checks, open a PR to
   `main`, and merge it after review and CI pass.
4. Update your local `main` and run the development release script:

   ```sh
   git switch main
   git pull --ff-only
   ./scripts/tag/dev-release.sh
   ```

Pushing either tag triggers the release workflow to build and publish the
package to PyPI and create a GitHub release. Stable releases require a dated
changelog heading matching the package version; development releases do not.
Merge release-workflow changes before tagging so the tagged commit includes
them.

## Commit and PR conventions

- Small, focused commits with imperative messages.
- Update `CHANGELOG.md` under `Unreleased` for user-visible changes.
- Update the documentation in `docs/` when behavior or the specification
  changes.

## Reporting bugs and requesting features

Use the GitHub issue templates for bug reports and feature requests. For
security vulnerabilities, do not open a public issue — see
[SECURITY.md](SECURITY.md).
