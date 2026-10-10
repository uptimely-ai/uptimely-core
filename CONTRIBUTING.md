# Contributing to Uptimely Core

Contributions are welcome via pull requests.

## Getting started

1. Fork the repository and clone your fork.
2. Open the repository in the included `.devcontainer/`, or install locally:

   ```sh
   poetry install --with test,dev,docs --extras "mcp s3"
   ```

3. Install the git hooks:

   ```sh
   poetry run pre-commit install
   ```

The devcontainer image installs Python tooling through
[`.devcontainer/install-python.sh`](.devcontainer/install-python.sh).
The script runs as root during the image build.
[`.devcontainer/post-create.sh`](.devcontainer/post-create.sh) installs the
project's Python and documentation dependencies as the container user.
Rebuild the devcontainer after changing its Dockerfile or image setup scripts.

### GitHub access from VS Code

Use an HTTPS Git remote to work with GitHub without starting an SSH agent.
The devcontainer does not require an SSH socket or mount your host's SSH
directory.

If your clone currently uses SSH, switch its remote in the integrated terminal:

```sh
git remote set-url origin https://github.com/uptimely-ai/uptimely-core.git
```

For a fork, substitute your fork's HTTPS URL. This changes only the remote URL,
not your commits or working files.

In the devcontainer window, use **Source Control** to commit, pull, and push.
When VS Code prompts for GitHub authentication, complete the browser sign-in.
If you already use an HTTPS credential helper on the host, Dev Containers
[shares those credentials](https://code.visualstudio.com/remote/advancedcontainers/sharing-git-credentials)
with the container automatically. Do not put access tokens in the devcontainer
configuration or repository files.

The included **GitHub Pull Requests** extension lets you browse, create, and
review pull requests and work with issues in the same VS Code window. Sign in
when the extension prompts; this does not require an SSH key.

SSH remains an optional alternative: Dev Containers automatically forwards an
existing host SSH agent when one is available. Without an agent, the container
can still start, but SSH Git operations need separate authentication setup.

## Previewing documentation

The site uses MkDocs with the Material theme for Markdown guides and mkdocstrings
for the Python API reference. Main navigation is in the left sidebar; the right
sidebar shows the current page's contents. Top navigation tabs are not enabled.
The devcontainer installs documentation dependencies through the optional Poetry
`docs` group. Outside the devcontainer, run `poetry install --with docs`.

Start the documentation preview from the repository root:

```sh
poetry run mkdocs serve --dev-addr 0.0.0.0:8000
```

Open <http://localhost:8000> using the forwarded port. MkDocs rebuilds the site
when documentation or Python source files change. Stop the server with `Ctrl+C`.
Architecture diagrams load Mermaid from a pinned CDN URL, so viewing diagrams
requires internet access.

Validate the complete site, including API generation and internal links:

```sh
poetry run mkdocs build --strict
```

The generated `site/` directory is ignored by Git. Edit guides in [`docs/`](docs/)
and navigation in [`mkdocs.yml`](mkdocs.yml). The
[API reference](docs/reference/api.md) selects public interfaces; their signatures
and Google-style docstrings come directly from `src/uptimely/`. Do not commit
generated API pages. When adding a public interface, include it in the reference
and document its arguments, return value, errors, and usage where applicable.

### Automatic publishing

[The documentation workflow](.github/workflows/docs.yml) builds the site on pull
requests and pushes to `main`. Warnings fail the build. Only successful builds
on `main` deploy to <https://uptimely-ai.github.io/uptimely-core/>. It can also
be run manually from the Actions tab.

Once per repository, open **Settings -> Pages -> Build and deployment** and
set **Source** to **GitHub Actions**. No personal access token or custom secret is
required. If the `github-pages` environment has deployment protection rules,
allow deployments from `main` or approve them as required by your organization.
Use this workflow as the site's only deployment mechanism.

## Workflow

1. Create a branch from `main`.
2. Make your change. Keep code modular, and add type hints and docstrings to
   new functions and classes (see `.github/copilot-instructions.md`).
3. Run the checks locally:

   ```sh
   poetry run pre-commit run --all-files
   poetry run pytest
   ```

4. Open a pull request against `main`. Describe the motivation and link any
   related issue. CI must pass (lint, format, tests, coverage gate) before
   merge.

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
  publishes to PyPI.
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
`release/*` branch. Keep the release PR focused on release metadata:

1. Choose the next version according to the versioning policy above.
2. Update `version` under `[project]` in [`pyproject.toml`](pyproject.toml).
   This is the active package version used to build distributions.
3. In [`CHANGELOG.md`](CHANGELOG.md), change `## [Unreleased]` to
   `## [<version>] - YYYY-MM-DD`, keeping its entries and categories, then add
   a fresh, empty `## [Unreleased]` section above it.
4. Name the branch `chore/prepare-<version>` (for example,
   `chore/prepare-0-2-0`), run the normal checks, and open a PR against `main`.
   Merge after review and CI pass.

After the release PR merges, check out the latest `main` with a clean working
tree and run the release-tag helper from the repository root:

```sh
git switch main
git pull --ff-only
./scripts/tag-release.sh
```

The script reads the version from Poetry, checks that it is a stable
`X.Y.Z` version, verifies that the checked-out `main` is clean and up to date
with `origin/main`, and refuses to reuse an existing tag. After confirmation,
it creates and pushes an annotated `v<version>` tag (for example, `v0.2.0`).
A Git tag names the exact commit it points to; create the release tag on the
merged release commit, where the package version matches the tag.

Pushing a `v*` tag triggers [`.github/workflows/release.yml`](.github/workflows/release.yml).
That workflow verifies the tag matches the version in `pyproject.toml`, builds
the package, checks the distributions with Twine, and publishes them to PyPI
using trusted publishing. The GitHub `release` environment and matching PyPI
trusted publisher must be configured for publication to succeed.

After a successful release, open a small follow-up PR to update
`pyproject.toml` to the next development version (for example,
`0.1.0` → `0.2.0.dev0`) so installs from the Git source are not mistaken for a
published release. This step is not automated. Keep a fresh `Unreleased`
section in the changelog; do not create a version heading for the development
version.

## Commit and PR conventions

- Small, focused commits with imperative messages.
- Update `CHANGELOG.md` under `Unreleased` for user-visible changes.
- Update the documentation in `docs/` when behavior or the specification
  changes.

## Reporting bugs and requesting features

Use the GitHub issue templates for bug reports and feature requests. For
security vulnerabilities, do not open a public issue — see
[SECURITY.md](SECURITY.md).
