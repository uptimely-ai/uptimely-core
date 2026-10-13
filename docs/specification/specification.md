# Open Analytics Specification

The specification is a single JSON document describing datasets, feature
dependencies, and function bindings. JSON is the canonical contract.
`Specification.from_python(...)` converts Python declarations to the same model;
`to_json(...)` exports it.

## Document Conventions

The root is one JSON object. Dimensions, entities, function templates, features,
arguments, and mappings use object keys as identifiers; do not repeat their
`id` inside those entries. Datasets are array entries and require an explicit
`id`. Identifiers should be stable, lowercase, and descriptive.

Tables describe the current parser contract. A default applies when a field is
omitted; it does not generally make explicit `null` valid. Unknown fields are
rejected. Python declarations and direct JSON authoring use the same canonical
model, rather than separate execution contracts.

## Root Object

| Field | JSON type | Required / default | Meaning |
| --- | --- | --- | --- |
| `name` | string or null | No; null | Display name. |
| `version` | string | No; `"0.1.0"` | Format version; only `0.1.0` is supported. |
| `source` | object | No; manual source | Authoring metadata. |
| `dimensions` | object | No; `{}` | Dimension definitions keyed by identifier. |
| `functions` | object | No; empty catalog | Reusable operation templates grouped by category. |
| `entities` | object | No; `{}` | Entity definitions keyed by identifier. |

When supplied, `source` requires `name` (string) and `generated` (boolean).
The default is `{"name": "manual", "generated": false}`. Python authoring
records `{"name": "python_api", "generated": true}`.

## Dimensions and Entities

A dimension identifies observations, such as a pump identifier or timestamp.
Each dimension declares `type`, optional `description`, and optional `parent`.
Parents must reference declared dimensions and must not form cycles.

An entity describes an analytical subject. It has a `name`, optional
`description`, a list of dimension identifiers, and a list of datasets.
The complete entity dimension key identifies a dataset observation.
Dimensions do not imply calculation partitioning.

### Dimension Fields

| Field | JSON type | Required / default | Meaning |
| --- | --- | --- | --- |
| `type` | string | Yes | Logical key type, such as `string`, `integer`, or `datetime`. |
| `description` | string or null | No; null | Explanation of the dimension. |
| `parent` | string or null | No; null | Bare identifier of a declared parent dimension. |

Parent metadata describes a hierarchy. It does not automatically add parent
columns to an entity, group calculations, or expand observations.

### Entity Fields

| Field | JSON type | Required / default | Meaning |
| --- | --- | --- | --- |
| `name` | string | Yes | Display name. |
| `description` | string or null | No; null | Explanation of the subject. |
| `dimensions` | array of strings | No; `[]` | Bare identifiers from the root dimension registry. |
| `datasets` | array of objects | No; `[]` | Datasets describing this subject. |

## Datasets

| Field | JSON type | Required / default | Meaning |
| --- | --- | --- | --- |
| `id` | string | Yes | Globally unique dataset identifier. |
| `description` | string or null | No; null | Explanation of the dataset. |
| `row_scope` | object | No; empty descriptions | Observation grain, filtering, and coverage. |
| `order` | array of objects | No; `[]` | Logical ordering by entity dimensions. |
| `features` | object | No; `{}` | Feature metadata keyed by identifier. |
| `mappings` | object | No; `{}` | Operations keyed by identifier, unique within this dataset. |

A mapping identifier names a binding instance, not a reusable function or an
output feature. Multiple mappings can invoke the same function with different
arguments. The catalog category of that function determines their operation
kind.

### Row Scope

`row_scope` contains descriptive strings:

- `grain`: what one observation represents.
- `filtering`: which observations belong to the dataset.
- `coverage`: expected completeness across dimension keys.

These descriptions do not execute filters or source queries.
Each field defaults to `""` and must be a string when supplied.

### Logical Order

```json
"order": [
  {"dimension": "$dimensions.timestamp", "direction": "asc"}
]
```

Order keys must be distinct dimensions of the owning entity. Directions are
`asc` or `desc`; array position determines key precedence. Omission means no
declared order. Null placement, collation, and ties are not specified.

Order is a logical convention, not a physical sort or partition guarantee.
Functions implement sorting and grouping themselves. Mapping context inherits
dataset order to interpret preceding and following observations.

## Feature Terminology

A feature is a column describing an entity, whether read from a source or
calculated. Its dataset registry declares the metadata once:

```json
"features": {
  "pump": {"type": "string"},
  "timestamp": {"type": "datetime"},
  "bearing_temperature": {"type": "float", "unit": "C"},
  "temperature_mean": {
    "type": "float",
    "description": "Trailing temperature mean",
    "unit": "C"
  }
}
```

Feature fields are `type`, `description`, and `unit`, all optional.
Each is a string or null and defaults to null.
Types should be declared explicitly: a dataframe return annotation cannot
describe the types of its individual columns.

Non-dimension feature identifiers must be globally unique and have exactly
one producer. Dimension columns can recur across datasets.

### Column Types and Dataframe Boundaries

The built-in engine accepts Polars `DataFrame` and `LazyFrame` results.
It validates non-null declared column types using these logical names:

| Logical type | Accepted Polars column type |
| --- | --- |
| `string` | String. |
| `integer` | Any integer type. |
| `float` | Any floating-point type. |
| `numeric` | Any numeric type. |
| `boolean` | Boolean. |
| `datetime` | Datetime, including timezone-aware datetime. |
| `date` | Date. |
| `object` | Struct or Object. |
| `array` | List or Array. |

No automatic type conversion is performed. Unknown logical column types fail
runtime validation; omitted feature types skip that column's type check.
Dimension types come from the root registry, even when their columns are not
listed as mapping outputs. Repeated dimension feature metadata does not
override the root dimension type.

Dataframe arguments refer to materialized datasets; they do not carry a
separate schema declaration. Entity dimensions and feature metadata define
the result's expected columns. A dataframe may carry extra columns, but only
the declared outputs and dimension keys enter the accumulated dataset.

## Functions

Templates declare an `entrypoint`, optional `description` where supported, and
an `args` schema. Each argument definition contains `type` and optional `comment`.

### Function Templates

Each category is an object keyed by function identifier and defaults to `{}`.
All templates require an `entrypoint` string and accept an `args` object,
defaulting to `{}`. Only vectorize templates currently support an optional
`description` string or null; other categories reject that field.

Entrypoints use `module.path:function_name` or
`path/to/module.py:function_name`. The module must be importable from the
project environment. For example:

```json
"vectorize": {
  "sum_features": {
    "entrypoint": "examples.example_2.functions.functions:sum_features",
    "args": {
      "dataset": {"type": "dataframe"},
      "left_feature": {"type": "string"},
      "right_feature": {"type": "string"},
      "output": {"type": "string"}
    }
  }
}
```

Use operation-oriented function names. Mapping identifiers and feature names
can differ from the template identifier. A bound function must resolve to
exactly one catalog category.

### Operation Types

| Category | Purpose | Result |
| --- | --- | --- |
| `read` | Read external observations. | Dataframe fragment. |
| `conform` | Adapt observations to the target row scope. | Dataframe fragment. |
| `expand` | Transfer or join observations into target dimensional coverage. | Dataframe fragment. |
| `collapse` | Calculate features at a coarser grain. | Dataframe fragment. |
| `vectorize` | Calculate features while preserving observation keys. | Dataframe fragment. |
| `write` | Persist or evaluate selected data. | Ignored; no output features. |

All data-producing functions return a dataframe. They perform their own
calculations, grouping, output naming, and scalar broadcasting.
Analytical functions should not perform external I/O.

### Argument Definitions

Common argument types include `string`, `integer`, `float`, `boolean`,
`dataframe`, `array`, and `object`. Homogeneous collections use recursive
expressions:

```json
"args": {
  "dataset": {"type": "dataframe"},
  "column": {"type": "string"},
  "window": {"type": "string"},
  "output": {"type": "string"},
  "partition_by": {"type": "array[string]"},
  "limits": {"type": "object{str: float}"}
}
```

Use plain `array` or `object` for heterogeneous or unspecified contents.
Argument types describe implementation values, not data dependencies.
Each argument requires a `type` string; `comment` is an optional string or null.
Nested expressions such as `object{str: array[string]}` are supported.

The parser checks bound argument names and explicit selector/type agreement;
it does not perform general validation or coercion of literal values against
the declared types, or verify that the callable accepts those arguments.
The compiler imports implementations and reads annotations, but column
schemas still come from the dimension and feature registries.
Use typed collections for nested dataframe references so the engine knows
which members to resolve as data.

## Feature Mappings

A mapping separates analytical requirements from the Python call:

```json
"temperature_mean": {
  "features": {
    "inputs": ["$features.bearing_temperature"],
    "outputs": ["$features.temperature_mean"]
  },
  "row_context": {
    "dimension": "$dimensions.timestamp",
    "before": {"time": "8h"},
    "after": {"time": "0s"}
  },
  "binding": {
    "function": "rolling_mean",
    "args": {
      "dataset": "$datasets.@.dataframe",
      "column": "$features.bearing_temperature.id",
      "window": "8h",
      "output": "$features.temperature_mean.id"
    }
  }
}
```

| Field | JSON type | Required / default | Meaning |
| --- | --- | --- | --- |
| `features` | object | No; empty lists | Explicit prerequisites and outputs. |
| `features.inputs` | array of strings | No; `[]` | Materialized features required before the call. |
| `features.outputs` | array of strings | No; `[]` | Features produced in the owning dataset. |
| `row_context` | object or null | No; null | Surrounding-observation requirements. |
| `binding` | object | Yes | Function invocation. |
| `binding.function` | string | Yes | Template identifier, resolving to exactly one category. |
| `binding.args` | object | No; `{}` | Concrete arguments matching the template schema. |

Input and output lists contain distinct `$features.<id>` references, without
selectors. Inputs establish dependencies even when not passed as arguments.
Conversely, passing a feature identifier is not a declaration that its data
must exist. Declare every consumed feature in `inputs`.

Outputs reference the owning dataset's feature registry. Entity dimension keys
are required in every returned dataframe, even when omitted from `outputs`.
A write mapping declares empty outputs and explicitly lists its required inputs.
Data-producing mappings require at least one output. Vectorize outputs cannot
redeclare entity dimensions. Collapse must produce at least one non-dimension
feature. There is no binding-level `return` field.

### Dimension-Keyed Alignment

The returned dataframe must contain the complete target dimension key and every
declared output column. Keys must be unique; dimensionless datasets allow at
most one row. Results are joined by keys, never by physical row position.
Null key values match corresponding null keys.

Only dimension columns and declared outputs are merged. A function may return
its input dataframe with added columns, but it cannot overwrite unrelated
features through that return. The engine checks declared output types.

Vectorize returns must preserve the dataset's exact observation keys, although
their physical order may differ. Other dataframe operations may change coverage
to construct their target row scope. The engine does not verify descriptive
grain, filtering, or coverage: non-vectorize fragments are full-joined and may
leave null feature values where another fragment has no matching observation.

### Structural Binding References

| Argument reference | Value passed to the function |
| --- | --- |
| `$features.<id>.id` | Feature identifier string. |
| `$dimensions.<id>.id` | Dimension identifier string. |
| `$datasets.<id>.dataframe` | Materialized dataframe for that dataset. |
| `$datasets.@.dataframe` | Current dataset's input-ready dataframe. |
| `$datasets.<id>.id` | Dataset identifier string; declare a `string` argument. |
| `$features.@.id` | The sole vectorize output, or sole non-dimension collapse output. |

Unsuffixed references remain supported; their template argument type determines
whether a dataset identifier is resolved to data. Prefer explicit selectors
when writing new declarations. `.id` arguments require `string`, and
`.dataframe` arguments require `dataframe`. Use only the reference forms above;
there is no generic JSON-path or attribute traversal.

`@` names the owning dataset, not its final completed state. Its required inputs
are materialized first. A single-output placeholder cannot be used with multiple
calculated outputs.

Other JSON values are literals. Runtime placeholders such as
`?storage.telemetry_source.path` remain unchanged during compilation and are
resolved against engine runtime resources. They do not establish dependencies.

Runtime placeholders have exactly the form
`?<namespace>.<object>.<attribute>`. For example, the engine resolves
`?storage.telemetry_source.path` from:

```json
{
  "storage": {
    "telemetry_source": {"path": "/data/telemetry.json"}
  }
}
```

Supply that mapping through `Engine(..., runtime_resources=...)`, not as a
specification root field. Missing namespaces, objects, or attributes are
execution errors. Plain literals and structural references do not change
between runtime environments.

### Python Declaration

```python
from uptimely.spec.python_spec import bind, feature, mapping, ref, row_context

calculation = mapping.Vectorize(
    id="temperature_mean",
    inputs=[ref.feature("bearing_temperature")],
    outputs=[feature.Feature(id="temperature_mean", type="float")],
    bind=bind.bind(
        rolling_mean,
        dataset=ref.current_dataset().dataframe,
        column=ref.feature("bearing_temperature").id,
        output=ref.feature("temperature_mean").id,
        window=row_context.time(
            "8h",
            dimension=ref.dimension("timestamp"),
            before="8h",
        ),
    ),
)
```

Python mapping declarations use `inputs` and `outputs`; conversion places them
under JSON `features`. Outputs can supply feature definitions directly or
reference definitions registered on the dataset.

## Collapse Mappings

Collapse functions receive a source dataframe and return a dataframe at the
target grain. For example:

```python
import polars as pl


def maximum(dataset: pl.LazyFrame, column: str, output: str) -> pl.LazyFrame:
    return dataset.group_by("pump").agg(pl.col(column).max().alias(output))
```

Declare this function under `functions.collapse`. Its binding can receive
`$datasets.telemetry.dataframe`, `$features.bearing_temperature.id`, and
`$features.bearing_temperature_max.id`.

Explicit inputs identify one source dataset, different from the target.
At least one input must be a non-dimension feature. Target dimensions must
exist in the source entity. To combine sources, use an expand mapping first.
The function, not the engine, performs grouping and names the returned columns.

## Vectorized Features

Vectorize mappings produce one or more feature columns at the existing dataset
grain. They may receive the current dataframe and return it with added columns,
or return just the dimension keys and output columns.

They do not return expressions, standalone series, dictionaries of expressions,
or scalars. Construct any literal-valued column inside the analytical function.

## Row Context

`row_context` belongs to the mapping, not its features or function template.
It describes the greatest required input reach across all calculations in that
mapping. It does not describe returned rows or alter full-dataframe execution.

| Field | Meaning |
| --- | --- |
| `dimension` | Required for `time` or `steps`; reference to a declared input dimension. |
| `before` | Required preceding context; defaults to `{}`. |
| `after` | Required following context; defaults to `{}`. |

Each direction is an object containing at most one measurement, or the string
`"unbounded"`. Both directions use the same measurement:

| Measurement | Allowed bound | Dimension |
| --- | --- | --- |
| `time` | Fixed duration, such as `"8h"`, or `"unbounded"`. | Datetime. |
| `steps` | Nonnegative integer or `"unbounded"`. | Integer. |
| `rows` | Nonnegative integer or `"unbounded"`. | None; uses dataset order. |

Only fixed dimension-based windows and row counts are supported. Feature-valued
axes and data-dependent window sizes are not supported.

```json
"row_context": {
  "before": {"rows": 1},
  "after": {"rows": 0}
}
```

An omitted or null context is unknown. Empty or zero directions explicitly mean
current-row-only context. Two unbounded directions require the whole input and
need no order; one unbounded direction still needs logical ordering.
There is no `extent`, mapping-level order, or partition metadata.
Functions handle grouping and sorting themselves.

Nonzero directional requirements need dataset order. A time/step dimension must
belong to the input entity and have the matching type. When directional context
requires ordering, that dimension must also occur in the dataset's order.
For collapse, validation uses the inferred source dataset rather than the target.

Fixed durations use distinct lowercase suffixes `w`, `d`, `h`, `m`, `s`, `ms`,
`us`, and `ns`. They are nonnegative, contain no whitespace, and have nanosecond
or coarser precision. A day is 24 hours; a week is seven days.

Python `row_context.time`, `steps`, and `rows` annotate bound values without
changing the values passed to functions. Time and step helpers require a
`dimension`. Nested annotations and direct mapping context are consolidated
using the maximum before and maximum after independently, not their sum.
All annotations must use the same measurement and dimension.

An eight-row rolling window including the current row needs seven preceding
rows. An eight-hour window ending two hours ago needs ten hours before.
Declarations must describe actual reach, not merely the window parameter.

Use `row_context.current()` for zero context and `row_context.dataset()` for
whole-input context. The canonical JSON records the consolidated requirements
explicitly; the compiler does not guess window semantics from argument names.

## Dependency Semantics

Explicit inputs establish producer-to-consumer edges. The compiler includes
required producers in feature-subset plans. Semantic validation rejects explicit
feature-dependency cycles; the compiler also requires an acyclic execution graph.
Argument identifiers alone do not establish feature dependencies.
Dataset dataframe arguments require their source observations to be available;
dataset `.id` arguments are metadata only. A dataframe argument does not imply
that all calculated features in that dataset are needed: declare consumed
features as inputs.

Vectorize and write inputs belong to their owning dataset. Other operations
can transfer data between datasets explicitly. Independent mappings can run in
the same plan stage.

## Validation Responsibilities

Structural validation rejects unsupported fields and malformed context.
Semantic validation checks identifiers, unique producers, input ownership,
function categories, argument names, context dimensions, and logical order.
Runtime validation checks materialized inputs, returned dataframe keys, output
columns and declared types, and vectorize observation preservation.

Validation cannot prove analytical correctness or infer a function's hidden
data dependencies. Functions and their declarations should be tested together.

## Write Mappings

Writes are ordinary entries under a dataset's `mappings`, not a separate
dataset-level `write` section. They have no feature outputs. For example:

```json
"write_telemetry": {
  "features": {
    "inputs": ["$features.temperature_mean"],
    "outputs": []
  },
  "binding": {
    "function": "write_telemetry",
    "args": {
      "dataset": "$datasets.@.dataframe",
      "columns": ["$features.temperature_mean.id"],
      "sink": "?storage.telemetry_sink.path"
    }
  }
}
```

Register a matching template in `functions.write` with `dataset: dataframe`,
`columns: array[string]`, and `sink: string` argument definitions. A possible
implementation is:

```python
import polars as pl


def write_telemetry(dataset: pl.DataFrame | pl.LazyFrame, columns: list[str], sink: str) -> None:
    selected = dataset.select(columns)
    if isinstance(selected, pl.LazyFrame):
        selected = selected.collect()
    selected.write_json(sink)
```

Explicit inputs establish dependencies; the `columns` argument tells the
implementation what to persist. They are independent declarations. Column-list
order does not schedule calculations, and feature-subset compilation does not
trim bound lists. Configured dataset sinks are retained in subset plans; a sink
requiring a feature outside the selected closure can fail with unavailable input.

## Complete JSON Example

This runnable example uses the repository's example functions to read two
integer columns and calculate their sum. The dimension key `id` is required in
returned dataframes but is not duplicated in the feature registry or outputs.

```json
{
  "name": "Sum example",
  "version": "0.1.0",
  "dimensions": {
    "id": {"type": "integer"}
  },
  "functions": {
    "read": {
      "read_data": {
        "entrypoint": "examples.example_2.functions.functions:read_data"
      }
    },
    "vectorize": {
      "sum_features": {
        "entrypoint": "examples.example_2.functions.functions:sum_features",
        "args": {
          "dataset": {"type": "dataframe"},
          "left_feature": {"type": "string"},
          "right_feature": {"type": "string"},
          "output": {"type": "string"}
        }
      }
    }
  },
  "entities": {
    "observation": {
      "name": "Observation",
      "dimensions": ["id"],
      "datasets": [
        {
          "id": "observations",
          "features": {
            "input_1": {"type": "integer"},
            "input_2": {"type": "integer"},
            "total": {"type": "integer"}
          },
          "mappings": {
            "read_inputs": {
              "features": {
                "inputs": [],
                "outputs": ["$features.input_1", "$features.input_2"]
              },
              "binding": {"function": "read_data"}
            },
            "calculate_total": {
              "features": {
                "inputs": ["$features.input_1", "$features.input_2"],
                "outputs": ["$features.total"]
              },
              "row_context": {},
              "binding": {
                "function": "sum_features",
                "args": {
                  "dataset": "$datasets.@.dataframe",
                  "left_feature": "$features.input_1.id",
                  "right_feature": "$features.input_2.id",
                  "output": "$features.total.id"
                }
              }
            }
          }
        }
      ]
    }
  }
}
```

Export or save this object, load it with `Specification.from_json(path)`, compile
it, and execute the plan. The resulting `(id, total)` rows are `(1, 3)` and
`(2, 7)`. Empty row context declares current-row-only calculation; no logical
order is needed for this elementwise sum.

## Migration

Replace mapping `features: ["name"]` with
`features: {"inputs": [...], "outputs": ["$features.name"]}`. Move feature-level
context to the producing mapping and remove `extent`. Add dimensions to
time/step context. Python mappings use `inputs=` and `outputs=`.
The canonical Python model is named `Mapping` (previously `FeatureMapping`);
update direct model imports and construction calls. The JSON key remains
`mappings`.

Update vectorize and collapse functions to receive their bound dataframes and
return dimension-keyed dataframe results. Grouping, aliases, and literal
construction are now the functions' responsibility. Re-export specifications
and recompile plans; old expression-based plans are not supported.
