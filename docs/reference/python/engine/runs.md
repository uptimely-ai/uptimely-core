# Saved runs

Use `RunStore` to read the latest run without running the project:

```python
import pathlib
from uptimely import run

store = run.RunStore(pathlib.Path("example"))
manifest = store.read_manifest()
sample = store.read_preview("pump_profile", run_id=manifest.run_id)
```

The optional `run_id` checks that the saved run has not changed since it was
read. Run storage keeps only the latest run, not run history.

::: uptimely.run.store
    options:
      heading_level: 2
      show_root_heading: false
      members: [RunStore, RunChangedError, RunNotFoundError]

::: uptimely.run.models
    options:
      heading_level: 2
      show_root_heading: false
      members: [RunManifest, ProfilePreview]
