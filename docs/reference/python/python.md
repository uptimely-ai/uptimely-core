# Python authoring

Use `uptimely` to describe profiles, dimensions, features, and calculations.
These declarations are converted to a Spec when you build a project. See the
[folder structure guide](../../architecture/folder-structure.md) for a runnable
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
            seed=up.Bind(read_telemetry),
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
            seed=up.Bind(
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

Use `up.ref` to refer to profile data, features, and other Spec values without
loading data during authoring. `up.ref.feature("name")` passes a feature's
identifier and declares an input dependency. Append `.id` to pass the identifier
without adding an input dependency, such as for an output column name. Use
`up.ref.paths("name")` for a file or directory configured in the project's
`paths` map. The Engine resolves relative paths against the project root before
invoking the function. Use `up.ref.params("name")` for a scalar configured in
`params`, which is passed unchanged.

`@up.function(returns=...)` describes what a function returns. Use
`"dataframe"` for a dataframe, `"none"` for no result, or `"any"` when the
result is intentionally ignored. The decorator records a contract; it does not
run the function or check that its calculations are correct. Function
signatures are checked when the project is compiled. External functions can be
referenced by `"package.module:function"` with `up.ref.function(...)`.

Use `read` for a function that returns a dataframe without taking a dataframe
input. A read may use `merge` to combine its returned fragment with the profile
data. Use `write` for a function that takes one dataframe and returns no result.
Use `compute` for transformations of data in the current profile. For
transformations that use another profile's dataframe, or return a fragment for
Uptimely to combine with existing data, use `stage` together with a merge binding such as
`merge=up.merge.default()`. Custom merge functions are also supported.

An optional `seed` names the assembly operator that initializes the profile
dataset. It must return a complete target dataframe, including every grain key,
and must use a `seed` binding without a merge or consuming the target dataset.
It can read external data or use a non-nullable dataframe from another profile.
Other fragments merge after the seed, regardless of assembly order. Profiles
without a seed retain their existing accumulation behavior.

Each operator declares one primary binding: `seed`, `read`, `compute`, `write`, or
`stage`. A stage requires a merge, while a read can optionally use one. The
generated Spec stores the primary binding as `compute`; function contracts and
dataframe inputs determine its operator kind. See the [engine reference](engine.md)
for runtime behavior.

For calculations that need nearby rows, see [Row context](row-context.md).

## API

::: uptimely.spec.python.spec
    options:
      heading_level: 2
      show_root_heading: false
      members: [Spec]

::: uptimely.spec.python.profile
    options:
      heading_level: 2
      show_root_heading: false
      members: [Profile, ProfileRegistry]

::: uptimely.spec.python.dimension
    options:
      heading_level: 2
      show_root_heading: false
      members: [Dimension, Resolution]

::: uptimely.spec.python.feature
    options:
      heading_level: 2
      show_root_heading: false
      members: [Feature, FeatureSet]

::: uptimely.spec.python.assembly
    options:
      heading_level: 2
      show_root_heading: false
      members: [Operator, Bind]

::: uptimely.spec.python.functions
    options:
      heading_level: 2
      show_root_heading: false
      members: [function]

::: uptimely.spec.python.ref
    options:
      heading_level: 2
      show_root_heading: false

::: uptimely.spec.python.row_context
    options:
      heading_level: 2
      show_root_heading: false
      members: [RowContextBinding, time, steps, rows, current, all_rows]
