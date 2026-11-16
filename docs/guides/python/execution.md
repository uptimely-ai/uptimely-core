# Execute analytics in Python {#execution-engine}

`Engine` runs a project's saved build bundle. It returns the resulting dataframes
and records a preview, logs, and run metadata under `artifacts/run/`.

```python
from uptimely import Uptimely

app = Uptimely()
result = app.run(validate=True)
```

Pass `validate=True` to enable
[runtime contract validation](../runtime-validation.md#runtime-validation).

To run one operator and its prerequisites, pass
`operator=("profile_id", "operator_id")` to `run()`. This does not rebuild the
project. See [Run artifacts](../../reference/formats/run.md) for saved output
and preview behavior.

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
