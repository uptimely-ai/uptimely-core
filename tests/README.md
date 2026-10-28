# Test layout

Tests are organized by the scope of the behavior they verify:

- `unit/` contains focused checks with small, isolated inputs.
- `integration/` contains checks that compose package subsystems, such as spec compilation, graph construction, and documentation generation.
- `examples/` verifies the documented, runnable projects under `examples/`.
- `fixtures/` contains reusable spec documents and portable execution plans. Add lengthy JSON setup here rather than embedding it in individual test modules.

Keep examples user-focused. Test-only scenarios and invalid inputs belong in fixtures or directly in focused unit tests.

## Running tests

Run `poetry run pytest` to build the example bundles required by the tests.

Full example bundles are built once by the test controller and shared read-only
with workers. Use `example_bundle()` to load fresh spec and plan objects, or
`copy_example_project()` when a test needs to modify or execute an isolated
project. Scoped example builds are prepared on demand once per worker and scope.

Explorer tests use `render_explorer()`, which reuses a saved plan for an unchanged
example spec. Pass an existing `plan=` when a custom spec has already been
compiled. New or modified specs are compiled normally, so invalid inputs still
exercise validation. Keep direct compilation and build calls in tests that
verify compiler or builder behavior, rather than using them as repeated setup.

The pre-commit pytest hook runs at the pre-push stage with four workers.

## Explorer JavaScript tests

The devcontainer and CI provide Node.js 24 LTS. Run the JavaScript tests
separately from pytest:

```sh
node --test tests/integration/explorer/*.cjs
```

These tests use Node's built-in test runner and need no npm dependencies.
