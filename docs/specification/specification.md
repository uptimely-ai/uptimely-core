# Open Analytics Specification

The Open Analytics Specification is a single JSON document that declares an analytical system: its data model, executable operation templates, and feature dependencies. It is the contract between a declarative analytical design and its implementation.

This document defines the format and semantic rules. Implementations may generate code from a specification, generate a specification from code, or validate the two independently. Compatibility means that an implementation interprets the documented structures and constraints consistently.

Python authoring is a convenience layer, not a second runtime contract. `Specification.from_python(...)` converts Python declarations into the canonical JSON model; the resulting model can be validated, documented, compiled, and exported with `to_json(...)`. Direct JSON authoring and Python-to-JSON generation must produce equivalent specification documents.

## Document Conventions

The root document MUST be a JSON object in one file. Object keys that identify resources are called identifiers and SHOULD be stable, lowercase, and descriptive. The tables in this reference use the following columns:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| Field name | JSON data type | `Yes`, `No`, or conditional | Meaning, allowed values, and constraints |

## Root Object

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | No | Human-readable name of the analytics specification. |
| `version` | string | Yes | Open Analytics specification version used by parsers and validators. |
| `source` | object | No | Authoring source metadata. `name` identifies the source (for example, `python_api`, `web_app`, or `manual`); `generated` is `true` when a framework generated the document and `false` when it was hand-written. If omitted, parsers treat the document as manually authored. |
| `dimensions` | object | No | Reusable identifiers and their hierarchies. |
| `functions` | object | Yes | Reusable `read`, `collapse`, `expand`, `conform`, `write`, `vectorize`, and `aggregate` function templates. |
| `entities` | object | Yes | Analytical entities, datasets, and operation bindings. |

## Feature Terminology

A feature is a named piece of information that describes an entity. The term includes both values loaded from a source and values derived during execution.

| Concept | Meaning | Declared under | Has a binding? |
| --- | --- | --- | --- |
| Feature | A named column in a dataset, with optional descriptive metadata. | `features` | No. |
| Mapping | An executable operation binding associated with zero or more output features. | `mappings` | Yes. |
| Aggregation | A reducer binding for one output feature of a collapse mapping. | The mapping's `aggregations` | Yes. |

Dimension columns may appear in multiple dataset feature registries. Other
feature identifiers MUST have one producer. Bindings use structural reference
strings for features, dimensions, and datasets; the compiler resolves them to
their identifiers. A mapping is a logical association, not an execution
fragment; the compiler may group mappings into physical fragments.

## Entities

An entity represents a real-world analytical subject, such as a pump, production line, or vehicle. `entities` is an object keyed by entity identifier. Entity dimension combinations SHOULD identify a coherent observation grain.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | Display name. |
| `description` | string | No | Human-readable explanation. |
| `dimensions` | array of strings | No | Dimension identifiers declared in the root `dimensions` object. |
| `datasets` | array of objects | No | Row-level views of this entity. |

## Datasets

A dataset is a conceptual data container for an entity. `features` declares
its columns; `mappings` associates those features with executable function
bindings. The operation category is inferred from the function's catalog
entry. Write bindings are output-free mappings in the same `mappings` object
as reads and transformations.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | string | Yes | Identifier unique within the entity. |
| `description` | string | Yes | Human-readable explanation. |
| `row_scope` | object | Yes | Conceptual row subset with `grain`, `filtering`, and `coverage` descriptions. |
| `order` | array of objects | No | Logical ordering by entity dimensions, in key-precedence order. Does not require physical sorting. |
| `features` | object | Yes | Feature metadata keyed by feature identifier. |
| `mappings` | object | Yes | Function bindings keyed by mapping identifier. |

### Feature and Mapping Identifiers

Each key under `features` names one feature. Each key under `mappings` names
one binding instance: a function reference together with its concrete
arguments, distinct from the reusable function template it invokes. Feature
mappings declare their output feature identifiers in `features`; write
mappings have an empty `features` list.

For collapse mappings, each entry in `aggregations` is a binding to one
`functions.aggregate` template. Its key names the feature it computes. The
shared collapse binding defines input and grouping behavior; reducer bindings
remain separate and are combined with it when the compiler builds execution
operations.

Mapping identifiers MUST be unique within their declaring dataset.

### Row Scope

Presented in the `row_scope` key of a dataset. A row scope describes the conceptual row subset for the dataset; runtime function arguments determine which rows are actually read from a source.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `grain` | string | Yes | Meaning of one row. |
| `filtering` | string | Yes | Selection criteria applied to the rows. Use an empty string when unfiltered. |
| `coverage` | string | Yes | Expected completeness of the dataset across its dimension keys, for example dense or sparse. Use an empty string when unspecified. |

### Logical Order

The optional dataset-level `order` array describes a logical ordering convention:

```json
"order": [
  {"dimension": "$dimensions.pump", "direction": "asc"},
  {"dimension": "$dimensions.timestamp", "direction": "desc"}
]
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `dimension` | string | Yes | Structural reference `$dimensions.<id>` to a dimension declared by the dataset's owning entity. |
| `direction` | string | Yes | `asc` for ascending or `desc` for descending order. |

Array position defines precedence: the first key is primary, the second breaks
ties in the first, and so on. Each dimension MUST appear at most once. Omitting
`order` or providing an empty array declares no ordering. Rows equal on all keys
have no specified relative order. Null placement and string collation are not
specified by this declaration.

This is descriptive metadata, not a persistent physical row-order contract.
Implementations MAY use it for sorting, source-query pushdown, presentation, or
optimization, or leave physical rows unordered. The declaration does not define
grouping or partitioning. Row-context requirements inherit these ordering keys,
but operations MUST NOT assume incoming rows physically follow dataset `order`.
The current batch engine does not sort automatically: a function whose
correctness depends on order must still implement ordering explicitly.

Python authoring uses the same keys and preserves their precedence:

```python
from uptimely.spec.python_spec import dataset, ref

telemetry = dataset.Dataset(
    id="telemetry",
    order=[
        dataset.Order(dimension=ref.dimension("pump"), direction="asc"),
        dataset.Order(dimension=ref.dimension("timestamp"), direction="desc"),
    ],
)
```

The owning entity must declare both dimensions.

### Dataframe Contract

At dataset boundaries, data is represented as a dataframe containing the entity dimensions and every materialized feature required by the dataset's calculations. It may contain additional columns. The specification does not require a wrapper or a particular dataframe library. Dataframes MUST be Apache Arrow compatible so implementations can exchange columnar data efficiently.

## Dimensions

Dimensions identify observations and establish an entity's grain. They are
reusable: a dimension may appear in multiple entities. A mapping's output
feature list includes dimension columns when it produces a dataframe. Dataset
feature metadata may therefore use the same identifier as a declared
dimension; the two identifiers belong to distinct namespaces.

`dimensions` is an object keyed by dimension identifier.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | string | Yes | Dimension data type, for example `string` or `datetime`. |
| `description` | string | No | Human-readable explanation. |
| `parent` | string | No | Identifier of another declared dimension that is this dimension's parent. |

## Functions

`functions` groups reusable operation templates by operation verb. A template describes a callable independent of the datasets or features that invoke it; `entrypoint` identifies the concrete implementation. Function identifiers SHOULD describe the operation, not the output feature or entity that happens to call it. Prefer identifiers such as `sum_features`, `extract_convergence_flag`, or `read_pump_telemetry` over identifiers such as `column_3`, `converged`, or `pump` when those shorter names would blur resources with operations.

| Operation type | Purpose | Input | Output | Purity |
| --- | --- | --- | --- | --- |
| `read` | Read data from an external source such as a file or database. | Source and literal arguments | Dataframe | No |
| `conform` | Return data that conforms to the target dataset's row scope. | Dataset and conform arguments | Dataframe | No |
| `expand` | Return data at expanded dimensional coverage. | Dataset and expansion arguments | Dataframe | No |
| `collapse` | Group source data and materialize aggregated features, usually at a different grain. | Dataset, grouping arguments, and reducer bindings | Dataframe | Yes |
| `aggregate` | Define one feature value derived within a collapse operation. | Feature references and literals | One aggregation expression | Yes |
| `vectorize` | Calculate one or more features from feature references and literals. | Feature references and literals | One element or a mapping of elements | Yes |
| `write` | Persist, print, or otherwise evaluate selected information. | Dataset, feature references, and literals | Implementation-specific | No |

### Function Templates

Each category under `functions` (`read`, `write`, `vectorize`, `aggregate`, `collapse`, `expand`, `conform`) contains reusable function templates keyed by function identifier.

| Field | Type | Required | Applies to | Description |
| --- | --- | --- | --- | --- |
| `entrypoint` | string | Yes | All | Executable implementation location, commonly `path/to/file.py:function_name`. |
| `description` | string | No | All | Human-readable explanation of the operation template. |
| `args` | object | No | All | Argument definitions keyed by argument name. |
| `partitioning` | string | No | `vectorize` | Engine partitioning expectation: `none`, `by_entity_dimensions`, or `custom`. |

### Argument Definitions

Each member of a template's `args` object defines one named argument. Values are supplied by a dataset operation or a feature binding, not by the template itself.

Function argument types are primitive implementation-facing types found in common programming languages. `dataframe` is a widely adopted structure for data processing and the most distinctive type in this list, but it is still a function argument contract rather than a binding reference type.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | string | Yes | Argument type, such as `string`, `integer`, `numeric`, `object`, `array`, or `dataframe`. Composite types use the syntax described below. |
| `comment` | string | No | Human-readable guidance for callers. |

Argument types may use compact recursive expressions for homogeneous collections. The expression is stored as one string in the `type` field:

| Expression | Meaning |
| --- | --- |
| `array[T]` | An array whose elements have type `T`. |
| `object{str: T}` | An object with string keys and values of type `T`. |

`T` may be a primitive type or another composite expression. For example:

```json
{
    "partition_by": {"type": "array[string]"},
    "limits": {"type": "object{str: float}"},
    "groups": {"type": "object{str: array[string]}"},
    "nested_values": {"type": "object{str: object{str: float}}"}
}
```

These expressions describe the function argument contract. Structural feature and dimension references map to `string`; structural dataset references map to `dataframe`. Use plain `array` or `object` when the element or value types are heterogeneous, empty, or otherwise unspecified.

## Feature Mappings

A mapping binds one function template to one or more output features. Its
operation category is inferred by looking up the bound function in the
function catalogs. A mapping using `read`, `collapse`, `expand`, or `conform`
MUST return a dataframe. The compiler and engine may combine compatible
mapping executions into physical fragments; those fragments are not declared
in the logical specification.

The dataset's `features` registry declares metadata once. A mapping's
`features` array references the registry entries it produces. Every
dataframe-producing mapping MUST include all entity dimensions in its outputs.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `binding` | object | Yes | The function identifier and concrete arguments. |
| `features` | array of strings | Yes | Feature identifiers produced by this mapping. |
| `aggregations` | object | Collapse only | Per-output reducer bindings for collapse mappings. |

For example, a mapping assigns source-provided columns to one read binding:

```json
"features": {
    "pump": {"type": "string"},
    "timestamp": {"type": "datetime"},
    "bearing_temperature": {
        "type": "float",
        "unit": "C",
        "description": "Drive-end bearing temperature"
    }
},
"mappings": {
    "telemetry": {
        "binding": {
            "function": "read_pump_telemetry",
            "args": {"source": "?storage.telemetry_source.path"}
        },
        "features": ["pump", "timestamp", "bearing_temperature"]
    }
}
```

### Dimension-Keyed Alignment

The engine aligns dataframe fragments, not individual features. Every
dataframe-producing mapping MUST produce all dimensions declared by its owning
entity. When mappings are combined, the engine joins their results by that
complete dimension key, never by row position. This places values for matching
observations in the same dataset rows so vectorize mappings can reference them
together. Returned row order may differ and mappings may use separate
resources. Duplicate dimension keys within one result are invalid because they
make alignment ambiguous.

A write binding receives the current dataset and the features it evaluates:

```json
"write": {
    "write_pump_telemetry": {
        "binding": {
            "function": "write_pump_telemetry",
            "args": {
                "sink": "?storage.pump_telemetry_sink.path",
                "dataset": "$datasets.@",
                "features": [
                    "$features.bearing_temperature_max",
                    "$features.health_signal_normalized"
                ]
                        }
    }
}
```

The feature list SHOULD follow dependency order when one calculated feature uses another. Compilation resolves each structural reference to its identifier. For a feature-subset plan, it includes only the selected identifiers. The write implementation combines the dataset and its named columns before writing:

```python
def write(dataset, features, sink):
    for feature in features:
        dataset = dataset.with_columns(pl.col(feature))
    dataset.collect().write_json(sink)
```

## Collapse Aggregations

Collapse is the dataframe-producing mapping that derives new feature values by
grouping a source dataset. `read`, `expand`, and `conform` mappings may load,
join, filter, reconcile, or otherwise change row coverage and arrangement.
Their function category is determined by the mapping binding's function
catalog entry. A collapse mapping has two layers: its `binding` supplies the
shared input and grouping arguments, and its `aggregations` bind one reducer
per output feature. Reducers reference templates in `functions.aggregate`;
the collapse function applies those expressions and returns the complete
dataframe for its declared output features.

```json
"features": {
    "pump": {"type": "string"},
    "bearing_temperature_max": {"type": "float"}
},
"mappings": {
    "pump_summary": {
        "binding": {
            "function": "collapse_features",
            "args": {
                "dataset": "$datasets.telemetry",
                "dimensions": ["$dimensions.pump"]
            }
        },
        "features": ["pump", "bearing_temperature_max"],
        "aggregations": {
            "bearing_temperature_max": {
                "function": "maximum",
                "args": {"feature": "$features.bearing_temperature"}
            }
        }
    }
}
```

The aggregate function itself does not declare an output-naming argument. The
aggregation key associates its result with a feature declared by the mapping.

## Vectorized Features

A feature is any dataframe column that describes an entity. All feature
metadata is declared once in the dataset's `features` registry. A mapping may
produce one or more outputs, including vectorized features.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `description` | string | No | Human-readable explanation. |
| `type` | string | No | Type of a source-provided feature; vectorized types may be inferred from function annotations. |
| `unit` | string | No | Unit of measure, for example `bar`, `kW`, or `mm/s`. |
| `row_context` | object | No | Input-observation requirements for a vectorized feature. Omission means unknown. |

Feature metadata does not contain function bindings. The function and concrete
arguments belong to a mapping. A vectorized mapping may list multiple output
features; when it does, its function MUST return a mapping from declared
feature identifiers to values. A one-output vectorized mapping may return a
single value directly.

### Vectorize Binding

A mapping whose binding function is declared under `functions.vectorize`
creates its listed output features. This category-based interpretation also
applies to the other operation function catalogs; the mapping itself does not
repeat a type field.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `function` | string | Yes | Identifier of a declared vectorize template. |
| `args` | object | No | Concrete argument values keyed by argument name. Structural references are plain strings. |

### Row Context

`row_context` describes the input observations required to calculate a vectorized feature.
Each calculated feature owns its requirement, interpreted using the dataset's
logical ordering and the function's partitioning contract. Features invoking the
same function can declare different context extents.

Context metadata is stored beside the feature's binding. Function arguments
retain their ordinary string, integer, array, or object values:

```json
{
  "binding": {
    "function": "rolling_mean",
    "args": {
      "column": "$features.temperature",
      "window": "8h"
    }
  },
  "row_context": {
    "extent": "bounded",
    "before": {"time": "8h"},
    "after": {}
  }
}
```

| Field | Values | Meaning |
| --- | --- | --- |
| `extent` | `bounded` (default), `partition`, `dataset` | Directional context, the whole input partition, or the whole input dataset. |
| `before` | Object, default `{}` | Required preceding observations in dataset logical order. |
| `after` | Object, default `{}` | Required following observations in dataset logical order. |

Choose one measurement for the feature's entire context, shared by `before`
and `after`:

| Measure | Value | Meaning |
| --- | --- | --- |
| `time` | Fixed-duration string | Elapsed time, for example `"8h"`. |
| `steps` | Nonnegative integer | Distance along an integer coordinate. |
| `rows` | Nonnegative integer | Number of ordered observations, regardless of coordinate gaps. |

Each measure also accepts `"unbounded"` for all observations in that direction
within the applicable input scope. Omit unused measurements; use `"0s"` or `0`
for an explicit zero extent.

For example, `before={"time": "8h"}` and `after={"time": "1h"}` use time in both
directions. Each direction can also be empty. An empty bounded context explicitly
declares current-row-only input. An omitted or `null` `row_context` is unknown.
Whole-partition and whole-dataset extents use empty directional objects.

Fixed durations use distinct lowercase suffixes: `w`, `d`, `h`, `m`, `s`, `ms`,
`us`, and `ns`. Examples include `"8h"`, `"1h30m"`, and `"1.5s"`. Days are exactly
24 hours and weeks exactly seven days. Durations are nonnegative, contain each
unit at most once, have no whitespace, and use precision of one nanosecond or
coarser. `"0s"` is zero time context.

Python authoring can annotate the existing argument directly:

```python
from uptimely.spec.python_spec import bind, feature, mapping, ref, row_context

features = [feature.Feature(id="temperature_mean", type="float")]

calculation = mapping.Vectorize(
    id="temperature_mean",
    bind=bind.bind(
        rolling_mean,
        column=ref.feature("temperature"),
        window=row_context.time("8h", before="8h"),
    ),
    features=[ref.feature("temperature_mean")],
)

lag = row_context.rows(
    "unbounded preceding",
    before=row_context.UNBOUNDED,
)
```

The positional value is passed unchanged to the function. `before` and `after`
are keyword-only; omitted directions default to zero within an annotation.
`row_context.steps(value, before=8)` measures coordinate distance rather than
row count. For an eight-row window including the current row, declare seven
preceding rows; an eight-row lag requires eight.

Annotations nested in arrays and objects are unwrapped recursively. Their
requirements consolidate into one mapping context using the maximum
extent in each direction. All contributing annotations and direct declarations
use the same measurement.
Unbounded dominates bounded values of the same measure. Declare the full extent
required by a calculation: an eight-hour window ending two hours ago requires
ten hours of preceding context.

Context can also be declared directly on the mapping using
`mapping.Vectorize(..., row_context=row_context.current())`,
`row_context.partition()`, or `row_context.dataset()`. Custom directional
declarations use the same `time`, `steps`, and `rows` helpers:

```python
calculation = mapping.Vectorize(
    id="temperature_delta",
    bind=bind.bind(
        temperature_delta,
        column=ref.feature("temperature"),
    ),
    features=[ref.feature("temperature_delta")],
    row_context=row_context.rows(1, before=1),
)
```

Direct metadata and argument annotations are merged using the same rules.
When a helper is supplied directly as mapping context, its context extent is
registered; its positional value is only passed to a function when the helper
is used in that function's bound arguments.

The compiler reads the output feature's context and preserves it on the corresponding
portable operation. When context is declared, the plan also includes planned
datasets' logical ordering and row-scope metadata. Each requirement describes
the operation's immediate input extent. The engine executes the function with
its ordinary bound arguments.

### Structural Binding References

Structural references in binding arguments use these forms:

```json
"$features.bearing_temperature"
```

The binding itself does not declare a type; only a function template's `args` schema does. The compiler resolves `$`-prefixed structural reference strings to plain identifiers:

| Reference | Resolves to | Meaning |
| --- | --- | --- |
| `$datasets.<id>` or `$datasets.@` | Dataset ID | A function template declares this argument as `dataframe`; the engine binds the live dataframe. |
| `$features.<id>` or `$features.@` | Feature ID | A function template declares this argument as `string`. |
| `$dimensions.<id>` | Dimension ID | A function template declares this argument as `string`. |
| Primitive types | JSON scalar, object, or array | Literal values passed through to the function, such as `string`, `float`, `integer`, `boolean`, `object`, or `array`. |

An aggregation entry is not a structural reference; it is a binding object with
`function` and `args` keys, declared in the collapse mapping's `aggregations`
object. Its `args` MUST include one or more source feature structural
references.

`$`-prefixed references are resolved once, by the compiler, into the compiled plan; they define the dependency graph and never change after compilation. A binding argument may instead hold a literal string starting with `?`, of the form `?<namespace>.<object>.<attribute>` (for example `?storage.telemetry_source.path`). The compiler leaves this form untouched — it is not a structural reference and does not participate in the dependency graph. Only the executing engine resolves it, against runtime resources supplied when the engine is constructed, so the same compiled plan can run against different physical locations in different environments without recompiling the specification.

Arrays can contain structural reference strings when an argument needs multiple references. Argument names SHOULD communicate the function's engine contract. Prefer specific names such as `pressure_features`, `health_features`, `optimization_features`, or `source` over generic names such as `columns` when the function expects a particular role.

Use a feature placeholder when a reusable vectorize function needs its output feature id:

```json
"output": "$features.@"
```

The parser replaces this value with the vectorize output feature id before invoking the function.
Because the placeholder denotes one output, it is only valid for a single-output
mapping. Multi-output mappings should use explicit feature references where an
output identifier is needed.

```json
"binding": {
    "function": "pressure_flow_efficiency",
    "args": {
        "df": "$datasets.@",
        "pressure_features": [
            "$features.discharge_pressure",
            "$features.flow_rate",
            "$features.motor_power"
        ]
    }
}
```

### Vectorize Function Contract

Each vectorize function receives feature elements from one dataset and scalar
configuration. A one-output mapping returns one element; a multi-output mapping
returns a mapping from feature identifiers to elements. An element may be a
lazy column expression, a materialized series, or another scalar or column
value supported by the executing backend.

Vectorize functions MUST NOT receive, filter, join, or otherwise mutate dataset dataframes. They should not perform I/O. Read and write functions may perform I/O.

## Dependency Semantics

Bindings for dataframe-producing mappings, vectorize mappings, and write operations form one
dependency graph. Typed references connect consumers to the operations that
produce their required datasets and features; aggregations contribute feature
dependencies to their enclosing collapse operation. Implementations MUST
evaluate every prerequisite before its consumers. Independent operations MAY be
evaluated in parallel.

## Validation Responsibilities

Implementations SHOULD validate the document before execution and validate function contracts in automated tests or CI. The specification can validate structure and data shape, but it cannot prove the business correctness of arbitrary function code.

| Validation area | Expected check |
| --- | --- |
| References | Dimensions, resources, templates, datasets, and bound feature dependencies resolve to declared identifiers. |
| Lineage | Every calculated feature has one producer and all feature identifiers are globally unique. |
| Dataset isolation | Every feature consumed by a calculation belongs to the same dataset as its output feature. |
| Types | Produced feature types agree with their declared or template-derived type. |
| Schema preservation | A vectorize function adds only its target column and preserves existing column names and types. |
| Data preservation | A vectorize function preserves existing values and does not decrease row count. |
| Dataset semantics | Read implementations honor the declared row scope: grain, filtering, and coverage. |
