---
name: release-preparation
description: "Prepare a stable or development Uptimely Core release. Use for release version bumps, changelog updates, reviewing commits since a release, and verifying completed roadmap items."
---

# Release preparation

Follow the release procedure in
[`CONTRIBUTING.md`](../../../CONTRIBUTING.md). Version metadata belongs in
[`pyproject.toml`](../../../pyproject.toml), not a `poetry.toml` file.

## Procedure

1. Confirm whether this is a stable or development release and determine the
   target version from the user's direction and the project's versioning policy.
   Ask if the target is ambiguous.
2. Inspect the current version, release tags, commits since the latest release,
   changelog entries, and relevant roadmap items. Use commit history to find
   user-visible changes that are missing from the changelog; do not duplicate
   already documented entries.
3. For a stable release, set the version in `[project]` in `pyproject.toml`,
   move the existing Unreleased entries under `## [<version>] - YYYY-MM-DD`, and
   add a fresh empty `## [Unreleased]` section above it.
4. For a development release, set the documented `X.Y.Z.devN` version and
   leave changelog entries under `Unreleased`.
5. Remove a backlog item only when changes on the current branch or merged
   history demonstrate it is complete. Preserve unfinished or merely planned
   work.
6. Run relevant checks and summarize edits. Do not create or push release tags,
   publish packages, or represent a release as published; those actions require
   an explicit request and follow the documented post-merge process.
