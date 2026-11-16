# Execution engine

`Engine` runs a project's saved build bundle. It returns the resulting dataframes
and records a preview, logs, and run metadata under `artifacts/run/`.

```python
from uptimely import Uptimely

app = Uptimely()
result = app.run(validate=True)
```

By default, the engine checks the bundle and its configuration but does not
validate every dataframe during execution. Set `validate=True` to check declared
input, output, key, and row-preservation rules. These checks do not determine
whether a calculation is correct; test expected results separately.

To run one operator and its prerequisites, pass
`operator=("profile_id", "operator_id")` to `run()`. This does not rebuild the
project, and each run replaces the latest saved run.

## Read a saved run

Use `RunStore` to read the latest run without running the project:

```python
import pathlib
from uptimely import run

store = run.RunStore(pathlib.Path("example"))
manifest = store.read_manifest()
sample = store.read_preview("pump_profile", run_id=manifest.run_id)
```

See the [Saved runs reference](../../reference/python/engine/runs.md)
for run consistency checks and storage interfaces.
