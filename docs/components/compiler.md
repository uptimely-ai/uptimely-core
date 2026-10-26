# Compiler

The Spec declares functions and mappings. A mapping says how a function is
used. The compiler records each mapping as an invocation, or planned step, and
orders the steps by their input features. The engine later loads and calls the
Python function named in the Spec. Compiling a plan does not run the analytics.

The build bundle contains both the plan and the Spec. The engine uses the Spec
for declarations and supplies runtime values when it runs each step.

This page describes the generated plan. Dataset, feature, function, and mapping
semantics are defined by the Spec document.

## Plan

A plan is one JSON object. Its root fields are:

| Field | JSON type | Meaning |
| --- | --- | --- |
| `plan_version` | integer | Portable plan format version, independent of `spec_version` and `build_version`. The current and only supported version is `2`. |
| `required_backend` | string | Dataframe backend required by the plan. The built-in compiler currently sets this to `polars`. |
| `resources` | object | Compiler-generated metadata not represented by the Spec, including inspected function return annotations and entrypoint package provenance. |
| `invocations` | array of objects | Operations to execute and their declared inputs and dependencies. |
| `stages` | array of arrays of strings | Invocation identifiers grouped by dependency order. |

All root fields are required. Unknown fields and unsupported versions are
rejected. Version 1 plans are not converted. Rebuild generated bundles from
their source Specs to create version 2 plans.

## Resources

The build bundle includes `spec.json`, which is the source of dimensions,
entities, functions, and datasets used by the engine. Plan resources contain
compiler-generated metadata that is not part of the Spec: inspected return
annotations keyed by invocation identifier and the installed distribution name
and version associated with each entrypoint. Signature-disabled functions have
no return-annotation entry, but their package provenance is read from installed
metadata without importing their implementation. Missing distribution metadata
is recorded as unavailable, while ambiguous namespace ownership is an error.
Package versions are informational and are not enforced by the engine. A plan
is consumed as part of its build bundle, not as a replacement for `spec.json`.

## Invocations

Each invocation represents one function-to-mapping application. Its inputs
declare the features used by that operation, while dependencies identify
invocations that must finish first. Invocation IDs are opaque references.
Consumers must not infer operation or identity metadata by parsing their
spelling.

| Field | JSON type | Meaning |
| --- | --- | --- |
| `id` | string | Unique identifier for this invocation. |
| `operation` | string | Operation category: `read`, `conform`, `expand`, `collapse`, `vectorize`, or `write`. |
| `entrypoint` | string | Implementation location for the function. |
| `function_id` | string | Function declaration used by the invocation. |
| `mapping_id` | string | Mapping declaration used by the invocation. |
| `entity_id` | string | Entity that scopes the invocation. |
| `dataset_id` | string or null | Dataset receiving or supplying dataframe state. |
| `arguments` | object | Resolved arguments passed to the function. Runtime storage placeholders remain unresolved. |
| `input_features` | array of strings | Features declared as inputs to the operation. |
| `output_features` | array of strings | Features produced by the operation. |
| `dependency_ids` | array of strings | Identifiers of invocation prerequisites. |
| `row_context` | object or null | Input row-context requirement, when declared. |

Structural references in Spec are resolved to plan identifiers. Runtime
dataframe binding is deferred to the engine. The `@` dataset reference denotes
the owning dataset for the operation's declared inputs, not a completed dataset
state.

## Stages

Each stage is a list of invocation identifiers. Every invocation appears exactly
once, and each dependency must appear in an earlier stage. Invocations in the
same stage are independent according to the declared dependency graph. An
engine may run them in parallel while preserving stage order.

## Dependencies

Mapping inputs define the feature dependencies used to select and order
invocations. Ordinary argument values do not establish dependencies by
themselves. A plan limited to selected features also includes the features they
depend on, along with configured writes for the selected datasets. Those writes
may use features outside the selection.

The dependency graph must be acyclic. Plan loading checks invocation
identifiers, dependency references, and stage ordering. These structural
checks do not prove that dependencies inside function implementations are
declared or that calculations are correct. The engine must support the plan
version and declared backend.

## Compilation and plan validation

The compiler accepts a loaded Spec and validates its current declarations
before compiling it into a valid, schedulable plan. Declaration rules are
defined in [Spec validation](spec.md#validation). Compilation checks
selected-feature feasibility, dependency ordering, plan schedulability, and
implementation entrypoints. Unless a function sets `validate_signature` to
`false`, it also inspects the Python signature and checks its return annotation
against the declared return contract. Disabling signature validation does not
disable Spec checks. Execution still requires a loadable function.

Plan loading checks supported versions and valid root fields, invocation IDs,
dependency references, and stage ordering. The compiler's generated stages
follow the dependency order. Loading a portable plan checks that its declared
stages preserve that order.

## API migration and rebuilding plans

Load the Spec, compile it, and save the plan with `uptimely.execution_plan`:

```python
from uptimely import compiler, execution_plan, spec

specification = spec.load_spec("spec.json")
plan = compiler.Compiler().compile(
    specification,
    features=["health_signal_normalized"],
)
execution_plan.export_json(plan, "execution_plan.json")
restored = execution_plan.from_json("execution_plan.json")
assert [invocation.id for invocation in restored.invocations] == [
    invocation.id for invocation in plan.invocations
]
```

Load a Spec with `uptimely.spec.load_spec` before passing it to `Compiler`.
Use `uptimely.execution_plan` to read and write plans, and use
`ExecutionPlan.invocations` to access the planned steps. Do not rely on the
format of their IDs.

Version 1 plans and bundles are not supported. Rebuild from the source Spec
with `uptimely build PROJECT_ROOT`.

The engine returns results: `result.datasets` contains final datasets,
`result.calculated_outputs` contains calculated features, and
`result.invocation_statuses` reports whether each planned step succeeded,
failed, or was skipped. `result.durations` and `result.failures` give more run
details.
