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

## Previewing project documentation

The documentation site uses MkDocs and mkdocstrings for the Python API
reference.

Start the documentation preview from the repository root:

```sh
poetry run mkdocs serve --dev-addr 0.0.0.0:8000
```

To include the pump analytics demo, first run the specification export and
documentation build commands from
[the documentation workflow](.github/workflows/docs.yml).

Open <http://localhost:8000> using the forwarded port. MkDocs rebuilds the site
when documentation or Python source files change. Stop the server with `Ctrl+C`.

### Automatic publishing

[The documentation workflow](.github/workflows/docs.yml) builds the site and
publishes it from `main`. It can also be run manually from the Actions tab.

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

### Changelog entries

For each pull request that changes behavior or adds something users can see,
add a concise entry under `## [Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md).
Use the relevant Keep a Changelog category, such as `Added`, `Changed`, or
`Fixed`. Describe the user impact rather than the implementation. Do not add a
version or date for an individual PR; release preparation moves these entries
under a version heading. Internal refactors and chores that do not affect users
do not normally need an entry.

## Branching strategy

This project uses **trunk-based development**:

- `main` is the only long-lived branch and is always releasable.
- Create short-lived branches off `main`, and merge them back via pull
  requests. Branch lifetimes are measured in days, not weeks.
- Releases are tags on `main` (`v0.1.0`, ...); there are no `develop` or
  `release/*` branches. Tagging a commit runs the CI release workflow that
  publishes to PyPI and GitHub Releases.
- Keep `main` green: merge changes that pass CI, and split large work into
  reviewable steps that each keep the test suite passing. Gate unfinished
  behavior behind an opt-in code path rather than a long-lived branch.
- Breaking changes land on `main` like everything else; the `0.x` version
  policy below covers them.

## Branch naming

Branches are named `<type>/<short-slug>`:

- `<type>` is one of `feature`, `fix`, `docs`, `refactor`, `chore`, `test`.
  Match the type to changelog intent: `feature` and `fix` usually produce a
  `CHANGELOG.md` entry, `refactor` and `chore` usually do not.
- `<short-slug>` is 2–5 lowercase hyphenated words describing what changes.

Examples: `feature/multi-output-calculations`, `fix/empty-spread-health-score`,
`docs/branching-strategy`. Prefix the slug with an issue number when one
exists (`fix/123-empty-spread`), but keep the issue link in the PR body too
(`Closes #123`).

Do not use personal namespaces, version numbers, or dates in branch names —
releases are tags, and branches are deleted on merge.

## Versioning

This project follows [Semantic Versioning](https://semver.org). While the
version is `0.x`, the API is unstable: minor releases may include breaking
changes, and patch releases may change behavior. From `1.0.0` onwards,
breaking changes will only ship in major releases, with deprecations
announced at least one minor release in advance.

### Preparing and publishing a release

Releases are prepared in a short-lived PR to `main`, not on a long-lived
`release/*` branch.

#### Stable releases

Keep the stable release PR focused on release metadata:

1. Choose the next version according to the versioning policy above.
2. Update `version` under `[project]` in [`pyproject.toml`](pyproject.toml).
   This is the active package version used to build distributions.
3. In [`CHANGELOG.md`](CHANGELOG.md), change `## [Unreleased]` to
   `## [<version>] - YYYY-MM-DD`, keeping its entries and categories, then add
   a fresh, empty `## [Unreleased]` section above it.
4. Name the branch `chore/prepare-<version>` (for example,
   `chore/prepare-0-2-0`), run the normal checks, and open a PR against `main`.
   Merge after review and CI pass.

After the release PR merges, run the stable release script from the repository
root:

```sh
git switch main
git pull --ff-only
./scripts/tag/stable-release.sh
```

The script checks the release version and repository state, then creates and
pushes the tag. The release workflow verifies the package version and
`CHANGELOG.md` heading before publishing.

After a stable release, open a follow-up PR to set the next development version
in `pyproject.toml` and keep a fresh `Unreleased` section in the changelog.

#### Development releases

For a development release, set the package version to a PEP 440 development
version in a PR to `main`, then merge it after review and CI pass. From the
repository root, run:

```sh
git switch main
git pull --ff-only
./scripts/tag/dev-release.sh
```

Increment the development release number for each upload; PyPI does not allow
replacing an already-published version. Keep changelog entries under
`Unreleased`.

#### PyPI and GitHub publishing

Pushing a release tag triggers
[`.github/workflows/release.yml`](.github/workflows/release.yml), which
publishes the package and creates a GitHub release. Merge workflow changes
before creating a tag so the tagged commit includes them.

## Commit and PR conventions

- Small, focused commits with imperative messages.
- Update `CHANGELOG.md` under `Unreleased` for user-visible changes.
- Update the documentation in `docs/` when behavior or the specification
  changes.

## Reporting bugs and requesting features

Use the GitHub issue templates for bug reports and feature requests. For
security vulnerabilities, do not open a public issue — see
[SECURITY.md](SECURITY.md).
