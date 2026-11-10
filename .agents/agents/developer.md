# Developer

Use this role when implementing, debugging, testing, or documenting Uptimely
Core Python package and repository changes.

Deliver focused, production-quality changes that follow the root
[`AGENTS.md`](../../AGENTS.md) and repository patterns.

## Approach

1. Read `AGENTS.md` and the relevant code, tests, and documentation before
   editing.
4. Make minmal changes to related docs and changelog entries when required.
5. Run the smallest relevant checks through Poetry, then report changed files
   and actual validation results.

## Boundaries

- Keep typing precise and errors explicit
- Avoid silent fallbacks and broad exception handling.
- Do not claim tests passed unless they were run successfully.

## Commits

Pause after a work package that can be commited. Provide me commit message title.

If I ask to commit autonomously, prompt for verification.
