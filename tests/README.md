# Test layout

Tests are organized by the scope of the behavior they verify:

- `unit/` contains focused checks with small, isolated inputs.
- `integration/` contains checks that compose package subsystems, such as specification compilation, graph construction, and documentation generation.
- `examples/` verifies the documented, runnable projects under `examples/`.
- `fixtures/` contains reusable specifications and portable execution plans. Add lengthy JSON setup here rather than embedding it in individual test modules.

Keep examples user-focused. Test-only scenarios and invalid inputs belong in fixtures or directly in focused unit tests.

## Running tests

Run `poetry run pytest` to export the example specifications required by the
tests and use four parallel worker processes by default.
Change the worker count with `-n`:

```sh
poetry run pytest -n 2     # Use two workers.
poetry run pytest -n auto  # Choose workers based on CPU cores.
poetry run pytest -n 0     # Run serially.
```

The pre-commit pytest hook runs at the pre-push stage with four workers.
