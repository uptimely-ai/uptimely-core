# Execute analytics in Python {#execution-engine}

`Engine` runs a project's saved build bundle. It returns the resulting dataframes
and records a preview, logs, and run metadata under `artifacts/run/`.

```python
# example
from uptimely import Uptimely

app = Uptimely()
result = app.run()
```

Analytical runtime validation and targeted operator execution are not currently
supported. See [Run artifacts](../artifacts/run.md) for saved output and preview
behavior.

## Read a saved run

Use `RunStore` to read the latest run without running the project:

```python
import pathlib
from uptimely import run

store = run.RunStore(pathlib.Path("example"))
manifest = store.read_manifest()
sample = store.read_preview("pump_profile", run_id=manifest.run_id)
```

See the [Saved runs reference](../python/engine-runs.md)
for run consistency checks and storage interfaces.
