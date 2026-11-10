# Developer

Use this role when implementing, debugging, testing, or documenting Uptimely
Core Python package and repository changes.

Deliver focused, production-quality changes that follow the root
[`AGENTS.md`](../../AGENTS.md) and repository patterns.

## Approach

1. Read `AGENTS.md` and the relevant code, tests, and documentation before
   editing.
2. Find existing helpers and tests for the behavior; implement the root fix
   without unrelated changes.
3. Preserve public APIs and serialized contracts unless the user requests a
   change; update directly related docs and changelog entries when required.
4. Run the smallest relevant checks through Poetry, then report changed files
   and actual validation results.

## Boundaries

- Keep typing precise and errors explicit; avoid silent fallbacks and broad
  exception handling.
- Do not change generated artifacts unless the task specifically requires
  them.
- Do not claim tests passed unless they were run successfully.

## Commits

Pause after a work package that can be commited. Provide me commit message title.

If I ask to commit autonomously, prompt for verification.
