# Uptimely Core agent instructions

## Project context

Uptimely Core is a Python package for declarative data-drivennumerical analytics in
industrial use cases. Specifications describe analytics workflows; the package
compiles them into plans, graphs, documentation, and executable workflows.

Before making project-wide changes, consult the relevant guides:

- [`readme.md`](../readme.md) for the project overview.
- [`docs/`](../docs/) for architecture, specification, and development details.
- [`examples/README.md`](../examples/README.md) for runnable example projects.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the contribution workflow and release process.

## Working principles

- Prefer clean, modular solutions that reuse existing code and remove
  unnecessary duplication.
- Prefer established, well-tested libraries and declarative configuration over
  custom mechanisms or hard-coded parameters.
- Update relevant documentation when behavior or public interfaces change.
- Run Python scripts and project commands through Poetry.
- Run the relevant tests after changes; run the unit test suite for substantial
  changes.

## Python conventions

- Add type hints to new or changed code and keep docstrings current.
- Define reusable literal values as module-level constants named in
  `UPPER_SNAKE_CASE` when practical.
- Write Google-style docstrings. Use `Args:`, `Returns:`, and `Raises:` sections
  when applicable.
- Import modules rather than individual classes, functions, or constants.
  Prefer `from parent import module` and qualify references, for example:

  ```python
  from uptimely import plan
  from uptimely.engine import backend

  callable = plan.Callable(...)
  dataframe_backend = backend.PolarsBackend()
  ```

- Keep imports at module scope. Use an alias if a module name conflicts with a
  local name.
- Use postponed annotations where they prevent circular-import problems.
  Guard type-only imports with `typing.TYPE_CHECKING`.
- Import optional dependencies at module scope with a guard, and report an
  explicit error if the feature is requested without that dependency.
- Preserve public re-exports from package `__init__.py` files.

## Documentation

- Write documentation in original, clear wording. Reorganize or expand existing
  material when it improves clarity or fills a gap.
- Keep documentation focused on user needs; avoid repeating details already
  expressed by scripts or configuration.

## Tooling

- Use local MCP servers when they are available and relevant to the task.
