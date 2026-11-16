# Python authoring

Use `uptimely` to describe profiles, dimensions, features, and calculations.
These declarations are converted to a Spec when you build a project. See the
[folder structure guide](../project-structure.md) for a runnable
example.

```python
import polars as pl
import uptimely as up

machine = up.Dimension(
    id="machine",
    resolutions=[up.Resolution(id="machine", key="machine", type="string")],
)
timestamp = up.Dimension(
    id="timestamp",
    resolutions=[up.Resolution(id="timestamp", key="timestamp", type="integer")],
)


def read_telemetry() -> pl.LazyFrame:
    return pl.LazyFrame(
        {
            "machine": ["pump_1", "pump_1"],
            "timestamp": [1, 2],
            "motor_bearing_temperature": [60, 65],
        }
    )


@up.function(returns="dataframe")
def maximum(
    dataset: pl.LazyFrame, feature: str, dimensions: list[str], output: str
) -> pl.LazyFrame:
    return dataset.group_by(dimensions).agg(pl.col(feature).max().alias(output))


class CoolingPumpTelemetry(up.Profile):
    id = "cooling_pump_telemetry"
    grain = [machine.resolution("machine"), timestamp.resolution("timestamp")]
    seed = "read_telemetry"
    assembly = [
        up.Operator(
            id="read_telemetry",
            outputs=[up.Feature(id="motor_bearing_temperature")],
            compute=up.Bind(read_telemetry),
        ),
    ]


class CoolingPump(up.Profile):
    id = "cooling_pump_summary"
    grain = [machine.resolution("machine")]
    seed = "summarize"
    assembly = [
        up.Operator(
            id="summarize",
            inputs=[up.ref.feature("motor_bearing_temperature")],
            outputs=[up.Feature(id="motor_bearing_temperature_max")],
            compute=up.Bind(
                maximum,
                dataset=up.ref.dataset("cooling_pump_telemetry"),
                feature=up.ref.feature("motor_bearing_temperature"),
                dimensions=up.ref.profile().grain.ids,
                output=up.ref.feature("motor_bearing_temperature_max").id,
            ),
        ),
    ]


specification = up.Spec(
    profiles=[CoolingPumpTelemetry, CoolingPump],
    name="Data-center cooling pump analytics",
)
```

When omitted, an operator ID is generated from its primary binding's function
ID, output interface, and an eight-character SHA-256 hash of that prefix. A
single output contributes its feature ID to the prefix. Otherwise, the output
count is used.
The operator referenced by a profile's `seed` must have an explicit ID.

## Profiles and features

A `Profile` describes the data at a particular level. Its `grain` selects the
dimension resolutions that identify its rows. `Dimension` defines those
resolutions and their dataframe key columns. Use `Profile.relations` to declare
links to other profiles; relations are not features and do not define row
identity.

Declare output metadata with `Feature`. A `FeatureSet` can group features for
reuse. Feature IDs are used in references and JSON. Names and descriptions are
for display. Logical feature types are available from
`uptimely.spec.feature_types`.

## Operators and functions

An `Operator` connects a function to a profile. Its `inputs` and `outputs`
declare feature dependencies and outputs, and its `Bind` takes a function
followed by its named arguments. If `inputs` is omitted, feature references in
the arguments are used to infer dependencies. Set `inputs=[]` to disable that
inference.

Every operator requires `compute=up.Bind(...)`. Add `merge` when its returned
fragment must be integrated into the target dataset.

### References

Use `up.ref` to refer to profile data, features, and other Spec values without
loading data during authoring. `up.ref.feature("name")` passes a feature's
identifier and declares an input dependency. Append `.id` to pass the identifier
without adding an input dependency, such as for an output column name. Use
`up.ref.paths("name")` for a file or directory configured in the project's
`paths` map. Use `up.ref.params("name")` for a scalar configured in `params`.
See [Paths and parameters](../../reference/configuration.md#paths-and-parameters)
for runtime resolution rules.

### Dataframe signatures

See [Function contracts](../../concepts/functions.md#function-contracts)
for dataframe counts, limits, and Explorer labels.

Unambiguous annotations infer `dataframe` or `none`. Otherwise, declare
`returns` through `@up.function(...)` or `up.ref.function(...)`.

### When to use merge

See [Fragment and merge](../../concepts/dataframes.md#fragment-and-merge)
for when a merge is needed and how results are accumulated.
Use the default merge explicitly:

```python
up.Operator(
    outputs=[up.Feature(id="pressure_limit")],
    compute=up.Bind(
        up.ref.function("project_io:read_limits", returns="dataframe"),
        source=up.ref.paths("limits_source"),
    ),
    merge=up.merge.default(),
)
```

A custom `up.Bind(...)` uses
`dataset=up.ref.dataset()` and `fragment=up.ref.fragment()` and returns the
complete target. Its dataset argument must allow `None` for initialization.

### Publication and opaque workflows

See [Publication](../../concepts/dataframes.md#publication) for output writers
and logical workflow outputs, and
[Function contracts](../../concepts/functions.md#function-contracts) for ignored results.

### Seeds and execution order

`Profile.seed` optionally names an explicitly identified operator returning the
initial complete dataset, without a merge or target input. It can read data or
transform a non-nullable foreign dataframe. Other merges follow the seed.
Profiles without one initialize through accumulation. Assembly grouping does
not replace dependency declarations.

### Grain relationships

Explorer compares source and target grains independently of function signatures.
See [grain relationships](../../concepts/grain-relationships.md#derived-grain-relationships) for
their meaning.

For calculations that need nearby rows, see [Row context](#row-context).

## Row context

Use a bare integer as row-count shorthand, and reference a declared direction
from the operator's binding arguments when the function also needs that value:

```python
import polars as pl
import uptimely as up
from uptimely.spec.row_context import RowContext


def rolling_mean(dataset: pl.DataFrame, value: str, output: str, before: int) -> pl.DataFrame:
    return dataset.with_columns(pl.col(value).rolling_mean(window_size=before + 1).alias(output))


up.Operator(
    id="rolling_mean",
    outputs=[up.Feature(id="mean")],
    row_context=RowContext(before=1),
    compute=up.Bind(
        rolling_mean,
        dataset=up.ref.dataset(),
        value=up.ref.feature("value"),
        output=up.ref.feature("mean").id,
        before=up.ref.row_context("before"),
    ),
)
```

See [Row-context utilities](../../reference/python/row-context.md)
for the types and extent contracts.
