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
the image. [`post-create.sh`](.devcontainer/scripts/post-create.sh) prepares
the repository after the container is created.

Scripts under [`scripts/`](scripts/) are repository convenience actions to run
in an existing development environment.

## Development process

1. **Branch:** Create a branch from `main`.
2. **Implement:** Make your change.
3. **Commit and validate:** Commit and push your changes. Installed pre-commit
   hooks run checks, including pytest when Python files are staged and Explorer
   JavaScript tests when Explorer JavaScript or test files are staged.
4. **Open a pull request:** Describe the motivation and open a PR against
   `main`. CI must pass lint, format, tests, and the coverage gate before merge.


## Multi-agent coding

Use the main VS Code window for `main` and basic tasks. For parallel agent work,
create a separate worktree and VS Code window per task. From the project root in
the devcontainer, create a detached worktree under `/home/vscode/worktrees`:

```sh
git worktree add --detach /home/vscode/worktrees/worktree-a main
```

Create and verify the task branch, then open the worktree in a new window:

```sh
git -C /home/vscode/worktrees/worktree-a switch -c feature/tune-explorer-layout
git -C /home/vscode/worktrees/worktree-a branch --show-current
code --new-window /home/vscode/worktrees/worktree-a
```

For an existing branch, omit `-c`. Each branch can be checked out in only one
worktree; commit from a task branch, not a detached worktree. Confirm the
intended branch before opening VS Code—opening a folder does not switch
branches. Keep each agent's changes separate and merge through the usual PR
process. Run `poetry install` if the worktree needs dependencies.

## Coding style

Follow the project's coding conventions in
[the repository's `AGENTS.md`](AGENTS.md).

### Changelog entries

For each pull request that changes behavior or adds something users can see,
add a concise entry under `## [Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md).
Use the relevant Keep a Changelog category, such as `Added`, `Changed`, or
`Fixed`. Describe the user impact rather than the implementation. Do not add a
version or date for an individual PR; release preparation moves these entries
under a version heading. Internal refactors and chores that do not affect users
do not normally need an entry.

### Testing

Run the Python suite with coverage and the Explorer JavaScript tests with:

```sh
poetry run pytest --cov --cov-report=xml
node --test tests/integration/explorer/*.cjs tests/unit/explorer/*.mjs
```

## Branching and releases

### Branching strategy

`main` is the only long-lived branch. Create short-lived branches from `main`,
keep changes small and CI-green, and merge through pull requests. Hide
unfinished work behind opt-in code paths. Releases are tags on `main`; there
are no `develop` or `release/*` branches.

Name branches `<type>/<short-slug>`:

| Prefix | Use |
| --- | --- |
| `feature` / `fix` | Add a capability or correct behavior. |
| `docs` | Change documentation. |
| `refactor` / `chore` | Restructure code or maintain the project. |
| `test` | Add or update tests. |

Use 2–5 lowercase, hyphenated words for the slug (for example,
`feature/multi-output-calculations`). Do not include personal names, versions,
or dates. User-visible features and fixes usually need a changelog entry;
internal refactors and chores usually do not.

### Versioning policy

We follow [Semantic Versioning](https://semver.org). Before `1.0.0`, minor
releases may break the API and patch releases may change behavior. After `1.0.0`,
breaking changes require a major release and at least one minor release of
deprecation notice.

### Preparing and publishing releases

Prepare releases in a short-lived PR to `main`. After review and CI pass, merge
the PR and run the release script from an up-to-date `main`; it checks the
version and repository state before tagging.

#### Stable release

1. **Prepare:** Choose the next `X.Y.Z` version, update `pyproject.toml`, and
   move `Unreleased` entries under a dated version heading in `CHANGELOG.md`.
   Add a fresh `Unreleased` section above it.
2. **Merge:** Open a release-preparation PR to `main`; merge after review and CI
   pass.
3. **Tag:** Update local `main` and run:

   ```sh
   git switch main
   git pull --ff-only
   ./scripts/tag/stable-release.sh
   ```

4. **Resume development:** Open a follow-up PR to set the next development
   version (for example, `0.3.0.dev0`). Keep the empty `Unreleased` section.

#### Development release

1. **Prepare:** Choose a PEP 440 `X.Y.Z.devN` version and increment `N` for each
   upload (published PyPI versions cannot be replaced). Update `pyproject.toml`;
   leave changelog entries under `Unreleased`.
2. **Merge:** Open a release-preparation PR to `main`; merge after review and CI
   pass.
3. **Tag:** Update local `main` and run:

   ```sh
   git switch main
   git pull --ff-only
   ./scripts/tag/dev-release.sh
   ```

Pushing either tag triggers the workflow to publish to PyPI and create a GitHub
release with the example project as a ZIP asset. The archive contains tracked
files from `example/`. Stable tags require a matching dated changelog heading;
development tags do not. Merge release-workflow changes before tagging.

## Commit and PR conventions

- Small, focused commits with imperative messages.
- Update `CHANGELOG.md` under `Unreleased` for user-visible changes.
- Update the documentation in `docs/` when behavior or the specification
  changes.

## Reporting bugs and requesting features

Use the GitHub issue templates for bug reports and feature requests. For
security vulnerabilities, do not open a public issue — see
[SECURITY.md](SECURITY.md).
