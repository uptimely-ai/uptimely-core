# Python authoring

Use `uptimely` to describe profiles, dimensions, features, and calculations.
These declarations are converted to a Spec when you build a project. See the
[project structure guide](../../project-layout/project-structure.md) for a runnable
example.

```python
import polars as pl
import uptimely as up

machine = up.Dimension(
    id="machine",
    resolutions=[up.Resolution(id="machine", key="machine", type="string")],
)


@up.function(returns="dataframe")
def maximum(
    dataset: pl.LazyFrame, feature: str, dimensions: list[str], output: str
) -> pl.LazyFrame:
    return dataset.group_by(dimensions).agg(pl.col(feature).max().alias(output))


class CoolingPump(up.Profile):
    id = "cooling_pump_summary"
    grain = [machine.resolution("machine")]
    assembly = [
        up.Operator(
            id="temperature_max",
            interface=up.Interface(
                outputs=[up.Feature(id="motor_bearing_temperature_max")],
            ),
            compute=up.Binding(
                function=maximum,
                arguments={
                    "dataset": up.ref.dataset("cooling_pump_telemetry"),
                    "feature": up.ref.feature("motor_bearing_temperature"),
                    "dimensions": up.ref.profile().grain.ids,
                    "output": up.ref.feature("motor_bearing_temperature_max").id,
                },
            ),
        ),
    ]


specification = up.Spec(profiles=[CoolingPump], name="Data-center cooling pump analytics")
```

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

An `Operator` connects a function to a profile. Its `Interface` declares input
and output features, and its `Binding` supplies the function and named
arguments. If `inputs` is omitted, feature references in the arguments are used
to infer dependencies. Set `inputs=[]` to disable that inference.

Use `up.ref` to refer to profile data, features, and other Spec values without
loading data during authoring. `up.ref.feature("name")` refers to a feature's
value; append `.id` when the function needs its identifier, such as an output
column name.

`@up.function(returns=...)` describes what a function returns. Use
`"dataframe"` for a dataframe, `"none"` for no result, or `"any"` when the
result is intentionally ignored. The decorator records a contract; it does not
run the function or check that its calculations are correct. Function
signatures are checked when the project is compiled. External functions can be
referenced by `"package.module:function"` with `up.ref.function(...)`.

Without a `merge` binding, a dataframe-producing function returns the complete
profile dataframe. To return a fragment for Uptimely to combine with existing
data, declare a merge binding, such as `merge=up.merge.default()`. Custom merge
functions are also supported. See the [engine reference](engine.md) for runtime
behavior.

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
      members: [Operator, Interface, Binding]

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
