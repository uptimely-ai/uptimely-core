# Prepare a release

Follow the `release-preparation` skill and
[`CONTRIBUTING.md`](../../CONTRIBUTING.md). Check the current package version
in `pyproject.toml`, the most recent release tag, commits since that release,
the `Unreleased` changelog, and the roadmap backlog.

If the release type or target version is unclear, ask before changing version
metadata. For stable releases, use the documented dated changelog heading and
leave a fresh `Unreleased` section. For development releases, keep entries
under `Unreleased`. Remove backlog items only when repository evidence confirms
the work is complete. Do not create or push tags, publish packages, or claim a
release is published.
