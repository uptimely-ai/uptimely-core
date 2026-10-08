---
group: specification
layout: default
title: Open Analytics Specification
parent: Specification
nav_order: 1
---

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
| `version` | string | Yes | Open Analytics specification version used by parsers and validators. |
| `dimensions` | object | No | Reusable identifiers and their hierarchies. |
| `functions` | object | Yes | Reusable `read`, `collapse`, `expand`, `conform`, `write`, `vectorize`, and `aggregate` function templates. |
| `entities` | object | Yes | Analytical entities, datasets, and operation bindings. |

## Feature Terminology

A feature is a named piece of information that describes an entity. The term includes both values loaded from a source and values derived during execution.

| Concept | Meaning | Declared under | Has a binding? |
| --- | --- | --- | --- |
| Retrieved feature | A source value returned unchanged by `read`, `conform`, or `expand`. | The corresponding operation map | Through its fragment binding. |
| Collapsed feature | New information generated while aggregating source features. | `collapse` | Through an aggregation. |
| Vectorized feature | One column produced by a vectorize operation. | `vectorize` | Yes. |
| Write | An operation that persists, prints, or evaluates dataset information. | `write` | Yes. |

Features use one shared identifier namespace, except that declared dimension columns may be repeated in dataframe fragments. Bindings use structural reference strings for features, dimensions, datasets, and fragments; the compiler resolves them to their identifiers.

## Entities

An entity represents a real-world analytical subject, such as a pump, production line, or vehicle. `entities` is an object keyed by entity identifier. Entity dimension combinations SHOULD identify a coherent observation grain.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | Display name. |
| `description` | string | No | Human-readable explanation. |
| `dimensions` | array of strings | No | Dimension identifiers declared in the root `dimensions` object. |
| `datasets` | array of objects | No | Row-level views of this entity. |

## Datasets

A dataset is a conceptual data container for an entity.

`read`, `conform`, `expand`, and `collapse` contain dataframe-producing fragment operations. `vectorize` contains single-feature calculations. `write` contains evaluation or persistence operations.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | string | Yes | Identifier unique within the entity. |
| `description` | string | Yes | Human-readable explanation. |
| `row_scope` | object | Yes | Conceptual row subset with `grain`, `filtering`, and `coverage` descriptions. |
| `read` | object | Yes | Read bindings keyed by fragment identifier. |
| `conform` | object | Yes | Conform bindings keyed by fragment identifier. |
| `expand` | object | Yes | Expand bindings keyed by fragment identifier. |
| `collapse` | object | Yes | Collapse bindings keyed by fragment identifier. |
| `vectorize` | object | Yes | Single-feature calculations keyed by output feature identifier. |
| `write` | object | Yes | Write bindings keyed by operation identifier. |

### Binding Identifiers

Every key under `read`, `conform`, `expand`, `collapse`, and `write`, and every feature key under `vectorize`, is a binding identifier. It names one binding: a function reference together with its concrete arguments, distinct from the function template identifier it invokes. A binding identifier is how a specification, a compiled plan, and a runtime engine each address one operation instance rather than the reusable function it calls.

An entry in a collapse binding's `aggregations` object is also a binding: it invokes one `functions.aggregate` template with concrete arguments and produces exactly one feature. Like the other categories, `aggregations` is an object; each key is the identifier of the feature the entry produces, so the framework supplies it to the function automatically instead of the function declaring its own output-naming argument.

Binding identifiers MUST be unique across the entire specification, not merely within their declaring dataset or entity. Tooling that addresses an operation by this identifier alone cannot resolve it unambiguously otherwise.

### Row Scope

Presented in the `row_scope` key of a dataset. A row scope describes the conceptual row subset for the dataset; runtime function arguments determine which rows are actually read from a source.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `grain` | string | Yes | Meaning of one row. |
| `filtering` | string | Yes | Selection criteria applied to the rows. Use an empty string when unfiltered. |
| `coverage` | string | Yes | Expected completeness of the fragment across its dimension keys, for example dense or sparse. Use an empty string when unspecified. |

A dataset has no persistent row-order contract. Operations that depend on order,
such as window calculations, MUST declare their ordering inputs explicitly.

### Dataframe Contract

At dataset boundaries, data is represented as a dataframe containing the entity dimensions and every materialized feature required by the dataset's calculations. It may contain additional columns. The specification does not require a wrapper or a particular dataframe library. Dataframes MUST be Apache Arrow compatible so implementations can exchange columnar data efficiently.

## Dimensions

Dimensions identify observations and establish an entity's grain. They are reusable: a dimension may appear in multiple entities. In the physical model, dimensions and features are usually columns, but dimensions are identifiers whereas features are analytical values.

`dimensions` is an object keyed by dimension identifier. Dimension identifiers MUST NOT duplicate feature identifiers.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | string | Yes | Dimension data type, for example `string` or `datetime`. |
| `description` | string | No | Human-readable explanation. |
| `parent` | string | No | Identifier of another declared dimension that is this dimension's parent. |

## Functions

`functions` groups reusable operation templates by operation verb. A template describes a callable independent of the datasets or features that invoke it; `entrypoint` identifies the concrete implementation. Function identifiers SHOULD describe the operation, not the output feature or entity that happens to call it. Prefer identifiers such as `sum_features`, `extract_convergence_flag`, or `read_pump_telemetry` over identifiers such as `column_3`, `converged`, or `pump` when those shorter names would blur resources with operations.

| Operation type | Purpose | Input | Output | Purity |
| --- | --- | --- | --- | --- |
| `read` | Read another dataset from an external source such as a file or database. | Source and literal arguments | Dataframe fragment | No |
| `conform` | Retrieve another dataset in the same entity and return a fragment that conforms to the target dataset's row scope. | Dataset and conform arguments | Dataframe fragment | No |
| `expand` | Retrieve another dataset at expanded dimensional coverage. | Dataset and expansion arguments | Dataframe fragment | No |
| `collapse` | Retrieve another dataset and materialize aggregated features, usually at a different grain. | Dataset and one or more aggregations | Dataframe fragment | Yes |
| `aggregate` | Define one feature value derived within a collapse operation. | Feature references and literals | One aggregation expression | Yes |
| `vectorize` | Calculate one new feature from one or more feature references. | Feature references and literals | One feature element | Yes |
| `write` | Persist, print, or otherwise evaluate selected information. | Dataset, feature references, and literals | Implementation-specific | No |

### Function Templates

Each category under `functions` (`read`, `write`, `vectorize`, `aggregate`, `collapse`, `expand`, `conform`) contains reusable function templates keyed by function identifier.

| Field | Type | Required | Applies to | Description |
| --- | --- | --- | --- | --- |
| `entrypoint` | string | Yes | All | Executable implementation location, commonly `path/to/file.py:function_name`. |
| `description` | string | No | All | Human-readable explanation of the operation template. |
| `args` | object | No | All | Argument definitions keyed by argument name. |
| `input_scope` | string | No | `vectorize` | Input extent required by the calculation: `row`, `dataset`, `window`, or `group`. |
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

These expressions describe the function argument contract. Structural feature and dimension references map to `string`; structural dataset and fragment references map to `dataframe`. Use plain `array` or `object` when the element or value types are heterogeneous, empty, or otherwise unspecified.

## Dataframe Fragment Operations

A fragment groups columns produced by one operation with one set of arguments. Its `read`, `collapse`, `expand`, or `conform` function MUST return a dataframe. A fragment contains dimension columns, which identify observations, and feature columns, which contain values describing those observations.

`features` is the fragment schema object. Despite its name, it declares both kinds of returned columns. Every fragment MUST include all dimensions declared by the owning entity so fragments can be combined without positional assumptions. The remaining entries declare the features produced by the fragment.

Every fragment item has a `binding` containing exactly the function reference and its arguments. Columns that need different bindings belong in different fragment items.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `binding` | object | Yes | The matching function identifier and concrete arguments. |
| `features` | object | Yes | Schema of returned dimension and feature columns, keyed by column name. All entity dimensions MUST be included. |

For example, a read operation binds a source identifier:

```json
"read": {
    "telemetry": {
        "binding": {
            "function": "read_pump_telemetry",
            "args": {
                "source": "?storage.telemetry_source.path"
            }
        },
        "features": {
            "pump": {"type": "string"},
            "timestamp": {"type": "datetime"},
            "bearing_temperature": {
                "type": "float",
                "unit": "C",
                "description": "Drive-end bearing temperature"
            }
        }
    }
}
```

### Dimension-Keyed Alignment

The engine aligns dataframe fragments, not individual features. Every fragment
MUST contain all dimensions declared by its owning entity. When fragments are
combined, the engine joins them by that complete dimension key, never by row
position. This places feature values for matching observations in the same
dataset rows so vectorize operations can reference them together. Fragment row
order may differ and fragments may arrive from separate resources. Duplicate
dimension keys within one fragment are invalid because they make alignment
ambiguous.

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

Collapse is the only dataframe fragment operation that derives new feature values. `read`, `expand`, and `conform` return existing feature values, although they may join, filter, reconcile, sort, or otherwise change row coverage and arrangement. Fragment operations obtain their input through their bindings: `read` reads an external source such as a file or database, while `conform`, `expand`, and `collapse` retrieve another dataset through `$datasets.<id>`. Collapse accepts one or more `aggregation` values, keyed by the feature identifier each one produces. Each aggregation references a function in `functions.aggregate`; the enclosing `functions.collapse` function evaluates those aggregations over the source dataset and returns the complete dataframe fragment for the target dataset. Each aggregation is itself a binding whose [binding identifier](#binding-identifiers) is its object key.

```json
"collapse": {
    "pump_summary": {
        "binding": {
            "function": "collapse_features",
            "args": {
                "dataset": "$datasets.@",
                "aggregations": {
                    "bearing_temperature_max": {
                        "function": "maximum",
                        "args": {
                            "feature": "$features.bearing_temperature"
                        }
                    }
                }
            }
        },
        "features": {
            "pump": {"type": "string"},
            "bearing_temperature_max": {"type": "float"}
        }
    }
}
```

The aggregate function itself does not declare an output-naming argument; the engine binds the produced value's identifier from the `aggregations` object key before returning the fragment.

## Vectorized Features

A feature is any dataframe column that describes an entity. Fragment columns are declared in each operation's `features` object; calculated features are declared in the dataset's `vectorize` object.

`vectorize` is keyed by output feature identifier. Each item invokes one vectorize function, consumes one or more `$features.<id>` values, and adds exactly one output feature.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `description` | string | No | Human-readable explanation. |
| `unit` | string | No | Unit of measure, for example `bar`, `kW`, or `mm/s`. |
| `binding` | object | Yes | The vectorize function and concrete arguments that produce the output feature. |

Calculated features do not declare a `type`. System reads the type automatically from the return annotation of the function referenced by `binding.function`.

### Vectorize Binding

A vectorize binding calls one `functions.vectorize` template to create its output feature. It is also the source of feature lineage. The framework translates binding values into concrete function arguments before execution.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `function` | string | Yes | Identifier of a declared vectorize template. |
| `args` | object | No | Concrete argument values keyed by argument name. Structural references are plain strings. |

Structural references in binding arguments use these forms:

```json
"$features.bearing_temperature"
```

The binding itself does not declare a type; only a function template's `args` schema does. The compiler resolves `$`-prefixed structural reference strings to plain identifiers:

| Reference | Resolves to | Meaning |
| --- | --- | --- |
| `$datasets.<id>` or `$datasets.@` | Dataset ID | A function template declares this argument as `dataframe`; the engine binds the live dataframe. |
| `$fragments.<id>` | Fragment ID | A function template declares this argument as `dataframe`; the engine binds the live dataframe. |
| `$features.<id>` or `$features.@` | Feature ID | A function template declares this argument as `string`. |
| `$dimensions.<id>` | Dimension ID | A function template declares this argument as `string`. |
| Primitive types | JSON scalar, object, or array | Literal values passed through to the function, such as `string`, `float`, `integer`, `boolean`, `object`, or `array`. |

An aggregation entry is not a structural reference; it is a bare object with `function` and `args` keys, passed only within a collapse binding's `aggregations` object. Its `args` MUST include one or more source feature structural references.

`$`-prefixed references are resolved once, by the compiler, into the compiled plan; they define the dependency graph and never change after compilation. A binding argument may instead hold a literal string starting with `?`, of the form `?<namespace>.<object>.<attribute>` (for example `?storage.telemetry_source.path`). The compiler leaves this form untouched — it is not a structural reference and does not participate in the dependency graph. Only the executing engine resolves it, against runtime resources supplied when the engine is constructed, so the same compiled plan can run against different physical locations in different environments without recompiling the specification.

Arrays can contain structural reference strings when an argument needs multiple references. Argument names SHOULD communicate the function's engine contract. Prefer specific names such as `pressure_features`, `health_features`, `optimization_features`, or `source` over generic names such as `columns` when the function expects a particular role.

Use a feature placeholder when a reusable vectorize function needs its output feature id:

```json
"output": "$features.@"
```

The parser replaces this value with the vectorize output feature id before invoking the function.

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

Each vectorize function receives feature elements from one dataset and scalar configuration and returns exactly one element for its calculated feature. An element may be a lazy column expression, a materialized series, or another scalar or column value supported by the executing backend.

Vectorize functions MUST NOT receive, filter, join, or otherwise mutate dataset dataframes. They should not perform I/O. Read and write functions may perform I/O.

## Dependency Semantics

Bindings for dataframe fragment, vectorize, and write operations form one
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
