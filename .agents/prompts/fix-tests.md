# Fix tests

Run both project test suites:

```sh
poetry run pytest
node --test tests/integration/explorer/*.cjs tests/unit/explorer/*.mjs
```

If either suite fails, inspect the failure output and relevant implementation
and tests. Fix the underlying cause with focused changes, adding or updating
regression tests when appropriate. Rerun both complete commands after making
changes, even if only one suite initially failed.

Report the commands run, their results, and any remaining failures. Do not claim
a suite passed unless it completed successfully.
