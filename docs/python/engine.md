# Execution engine

`Engine` runs a project's saved build bundle. It returns the resulting dataframes
and records a preview, logs, and run metadata under `_generated/run/`.

```python
from uptimely import Engine, Project

result = Engine(Project().load_build_bundle()).run(validate=True)
```

By default, the engine checks the bundle and its configuration but does not
validate every dataframe during execution. Set `validate=True` to check declared
input, output, key, and row-preservation rules. These checks do not determine
whether a calculation is correct; test expected results separately.

To run one operator and its prerequisites, pass
`operator=("profile_id", "operator_id")` to `run()`. This does not rebuild the
project, and each run replaces the latest saved run.

## Engine and configuration

::: uptimely.engine.engine
    options:
      heading_level: 2
      show_root_heading: false
      members: [Engine]

::: uptimely.engine.config
    options:
      heading_level: 2
      show_root_heading: false
      members: [Config, EngineConfig, EngineBackendConfig, Params, ParameterConfig]

## Results

`datasets` contains the final dataframe for each profile.
`calculated_outputs` contains feature outputs, keyed by profile and feature ID.
`invocation_statuses`, `durations`, and `failures` describe each executed step.
`preview_frames` holds collected samples; `preview_failures` reports previews
that could not be made.

::: uptimely.engine.runtime.result
    options:
      heading_level: 2
      show_root_heading: false
      members: [ExecutionResult]

## Saved runs

Use `RunStore` to read the latest run without running the project:

```python
import pathlib
from uptimely import run

store = run.RunStore(pathlib.Path("examples/pump_analytics"))
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

## Dataframes and merge functions

`Dataset` stores a profile's accumulated dataframe. `Fragment` represents the
data returned by a calculation. `Merge` combines a fragment with the dataset.
`merge_by_grain` is the built-in Polars merge function; provide a custom merge
function when the built-in behavior does not fit.

::: uptimely.engine.dataframe.dataset
    options:
      heading_level: 2
      show_root_heading: false
      members: [Dataset]

::: uptimely.engine.dataframe.fragment
    options:
      heading_level: 2
      show_root_heading: false
      members: [Fragment]

::: uptimely.engine.dataframe.merge
    options:
      heading_level: 2
      show_root_heading: false
      members: [Merge]

::: uptimely.library.merge.polars
    options:
      heading_level: 2
      show_root_heading: false
      members: [merge_by_grain]

## Dataframe backends

The engine includes a Polars backend and supports eager and lazy dataframes.
Implement `DataFrameBackend` to provide another backend.

::: uptimely.engine.dataframe.backend
    options:
      heading_level: 2
      show_root_heading: false
      members: [DataFrameBackend, PolarsBackend]
