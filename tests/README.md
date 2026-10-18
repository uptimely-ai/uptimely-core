# Test layout

Tests are organized by the scope of the behavior they verify:

- `unit/` contains focused checks with small, isolated inputs.
- `integration/` contains checks that compose package subsystems, such as spec compilation, graph construction, and documentation generation.
- `examples/` verifies the documented, runnable projects under `examples/`.
- `fixtures/` contains reusable spec documents and portable execution plans. Add lengthy JSON setup here rather than embedding it in individual test modules.

Keep examples user-focused. Test-only scenarios and invalid inputs belong in fixtures or directly in focused unit tests.

## Running tests

Run `poetry run pytest` to build the example bundles required by the tests.

The pre-commit pytest hook runs at the pre-push stage with four workers.
