# Uptimely Core agent instructions

## Project context

Uptimely Core is a Python package for declarative, data-driven numerical
analytics in industrial use cases. Specifications describe analytics workflows;
the package compiles them into plans, graphs, documentation, and executable workflows.

Before making project-wide changes, consult the relevant guides:

- [Project overview](readme.md)
- [Documentation](docs/)
- [Runnable examples](examples/README.md)
- [Contribution workflow and release process](CONTRIBUTING.md)

## Working principles

- Prefer clean, modular solutions that reuse existing code and remove
  unnecessary duplication.
- Prefer established, well-tested libraries and declarative configuration over
  custom mechanisms or hard-coded parameters.
- Run Python scripts and project commands through Poetry.
- Run the relevant tests after changes; run the unit test suite for substantial
  changes.

## Python conventions

- Add type hints to new or changed code and keep docstrings current.
- Define reusable literal values as module-level constants named in
  `UPPER_SNAKE_CASE` when practical.
- Write Google-style docstrings for uptimely-core package modules, classes, and functions.
  Use `Args:`, `Returns:`, and `Raises:` sections when applicable.
- Write NumPy-style docstrings in the examples package modules, classes, and
  functions; do not include data types.
- Import modules rather than individual classes, functions, or constants.
  Use absolute imports from the owning package across packages
  (`from uptimely.compiler import plan`), and relative imports for siblings
  (`from . import backend`). Avoid multi-level relative imports.
- Keep imports at module scope. Use an alias if a module name conflicts with a
  local name.
- Model the solution to Python classes over function modules.
- Separate stateless and stateful logic into different classes.

## Documentation
- Update relevant documentation on significant public interfaces change.
- Write documentation in original, clear wording. Reorganize or expand existing
  material when it improves clarity or fills a gap.
- Keep documentation focused on user needs; avoid repeating details already
  expressed by scripts or configuration.
- In project root readme.md, only code edits are allowed
- Mirror the root readme changes to docs/index.md
- Do not use semicolons ;
- Do not use word canonical

## Breaking changes
- Breaking changes are allowed on version 0.x.x
- Prefer breaking changes when it significantly improves solution architecture
- During 0.x.x structure might change significantly: Prefer full refactoring, and acommodate tests to new code

## Tooling

- Use local MCP servers when they are available and relevant to the task.
