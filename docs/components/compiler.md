# Compiler

The compiler converts a Spec document into a portable execution
plan. The plan records the operations, their dependencies, and the runtime
resources an engine needs. It does not contain the compiler's in-memory graph
or execute analytical functions.

This page describes the generated plan. Dataset, feature, function, and mapping
semantics are defined by the Spec document.

## Plan

A plan is one JSON object. Its root fields are:

| Field | JSON type | Meaning |
| --- | --- | --- |
| `plan_version` | string | Portable plan format version, independent of `spec_version` and `build_version`. The current and only supported version is `0.2.0`. |
| `required_backend` | string | Dataframe backend required by the plan. The built-in compiler currently sets this to `polars`. |
| `resources` | object | Runtime metadata needed by the engine. |
| `callables` | array of objects | Operations to execute and their declared inputs and dependencies. |
| `stages` | array of arrays of strings | Callable identifiers grouped by dependency order. |

All root fields are required. Unknown root fields and unsupported plan versions
are rejected.
Increment `plan_version` when the portable plan format changes incompatibly.

## Resources

Resources copy the parts of Spec needed to interpret the plan. They allow
an engine to load the plan without the original Spec document.

| Resource | Contents |
| --- | --- |
| `dimensions` | Dimension definitions keyed by identifier. |
| `entities` | Entity identifiers and their dimension identifiers. |
| `functions` | Function templates used by the callables. |
| `datasets` | Dataset features, logical order, and row scope, keyed by dataset identifier. |
| `signatures` | Inspected return annotations keyed by callable identifier. Functions with signature validation disabled have no entry here. |

## Callables

Each callable represents one function invocation. Its inputs declare the
features used by that operation; dependencies identify callable invocations
that must finish first.

| Field | JSON type | Meaning |
| --- | --- | --- |
| `id` | string | Unique identifier for this invocation. |
| `operation` | string | Operation category: `read`, `conform`, `expand`, `collapse`, `vectorize`, or `write`. |
| `entrypoint` | string | Implementation location for the function. |
| `entity_id` | string | Entity that scopes the invocation. |
| `dataset_id` | string or null | Dataset receiving or supplying dataframe state. |
| `output` | string or null | Primary output identifier. |
| `arguments` | object | Resolved arguments passed to the function. Runtime storage placeholders remain unresolved. |
| `input_features` | array of strings | Features declared as inputs to the operation. |
| `output_features` | array of strings | Features produced by the operation. |
| `dependency_ids` | array of strings | Identifiers of callable prerequisites. |
| `row_context` | object or null | Input row-context requirement, when declared. |

Structural references in Spec are resolved to plan identifiers. Runtime
dataframe binding is deferred to the engine. The `@` dataset reference denotes
the owning dataset for the operation's declared inputs, not a completed dataset
state.

## Stages

Each stage is a list of callable identifiers. Every callable appears exactly
once, and each dependency must appear in an earlier stage. Callables in the same
stage are independent according to the declared dependency graph; an engine may
run them in parallel while preserving stage order.

## Dependencies

Mapping inputs define the feature dependencies used to select and order
callables. Ordinary argument values do not establish dependencies by
themselves. A plan limited to selected features also includes the features they
depend on, along with configured writes for the selected datasets. Those writes
may use features outside the selection.

The dependency graph must be acyclic. Plan loading checks callable identifiers,
dependency references, and stage ordering. These structural checks do not prove
that dependencies inside function implementations are declared or that
calculations are correct. The engine must support the plan version and declared
backend.

## Validation

Compiler validation checks that a Spec document can be compiled into a
valid, schedulable plan:

- Spec declarations are semantically validated directly, without creating a
  separate resolved spec. The compiler builds one invocation node per mapping
  and resolves structural arguments when producing plan callables.
- Selected output features exist, and the dependency graph is acyclic.
- Function entrypoint syntax is checked. Unless a function sets
  `validate_signature` to `false`, its implementation is loaded, its Python
  signature is inspected, and its return annotation is checked against the
  declared return contract. Disabling signature validation does not disable
  spec-level contract or dependency validation, and the implementation must
  still be loadable at execution time.
- Loaded plans use a supported version and valid root fields, callable IDs,
  dependency references, and stage ordering.
