# Compiler

The Spec declares functions and operators. An operator says how a function is
used. Today, each operator's compute binding becomes a plan invocation; a
fragment-producing operator may also have a separate merge invocation. The
compiler orders these steps by their input features. It does not yet rewrite or
combine operator work through optimization. The engine later loads and calls
the Python function named in the Spec. Compiling a plan does not run the
analytics.

The current correspondence between Spec operators and plan invocations is an
implementation choice, not a required one-to-one relationship. Future compiler
optimization strategies may split, combine, or otherwise transform operator
work, making it important to distinguish a Spec operator (the declared
operation) from a plan invocation (an executable step).

The build bundle contains both the plan and the Spec. The engine uses the Spec
for declarations and supplies runtime values when it runs each step.

This page describes the generated plan. Profile, feature, function, and operators
semantics are defined by the Spec document.

## Plan

A plan is one JSON object. Its root fields are:

| Field | JSON type | Meaning |
| --- | --- | --- |
| `plan_version` | integer | Portable plan format version, independent of `spec_version` and `build_version`. The current and only supported version is `9`. |
| `required_backend` | string | Dataframe backend required by the plan. The built-in compiler currently sets this to `polars`. |
| `invocations` | array of objects | Operations to execute and their declared inputs and dependencies. |
| `stages` | array of arrays of strings | Invocation identifiers grouped by dependency order. |

All root fields are required. Unknown fields and unsupported versions are
rejected. Earlier plan versions are not converted. Rebuild generated bundles
from their source Specs to create version 9 plans.

## Invocation metadata

The build bundle includes `spec.json`, which remains the source of dimensions,
profiles, functions, and operators used by the engine. Each invocation carries
its implementation return annotation and entrypoint package provenance.
Signature-disabled functions have no return annotation. Package provenance is
read independently without importing the implementation; missing distribution
metadata is recorded as unavailable, while ambiguous namespace ownership is an
error. Package versions are informational and are not enforced by the engine.
A plan is consumed as part of its build bundle, not as a replacement for
`spec.json`.

## Invocations

Each invocation represents one executable function application associated
with a Spec operator. Its inputs
declare the features used by that operation, while dependencies identify
invocations that must finish first. Invocation IDs are opaque references.
Consumers must not infer operation or identity metadata by parsing their
spelling.

Compiler-generated IDs use `<operator-label>--<fingerprint>`, for example
`bearing-temperature-delt--<10-hex-digits>`. Labels use lowercase ASCII letters,
digits, and single dashes, with a maximum of 24 characters.
Operators without ASCII letters or digits
use the label `invocation`. The fingerprint is the first 10 hexadecimal
characters of SHA-256 over the compact JSON array
`[function_id, profile_id, operator_id]`. The full declaration
identifiers are hashed before label normalization or truncation.

IDs are at most 36 characters and stay stable across recompilation and feature
selection when these identity fields are unchanged. Argument or implementation
changes do not change the ID; it identifies a declared invocation, not a build
or execution. Operator kind is not part of the label or fingerprint. Compute
and merge invocations use the same operator label and are distinguished by
their function IDs. Compilation rejects ID collisions rather than overwriting a
node. Use the invocation's separate metadata fields for full names and meaning.
Rebuild existing bundles to adopt compact IDs consistently in plans, run logs,
and Explorer. Version 8 stores inspected function and package metadata on each
invocation instead of in a separate `resources` object. Version 7 replaced
invocation `dataset_id` with `profile_id`, without a legacy alias. Datasets are
engine-owned runtime accumulators, not invocation declaration metadata.

| Field | JSON type | Meaning |
| --- | --- | --- |
| `id` | string | Unique identifier for this invocation. |
| `role` | string | Binding position: `compute` or `merge`. |
| `result` | string | Result handling: `none`, complete `target`, or staged `fragment`. |
| `operator_kind` | string | Derived operator label: `read`, `conform`, `expand`, `collapse`, `vectorize`, `write`, or `escape`. Merge invocations retain their owning operator's label. |
| `entrypoint` | string | Implementation location for the function. |
| `function_id` | string | Function declaration used by the invocation. |
| `operator_id` | string | Operator declaration used by the invocation. |
| `profile_id` | string or null | Declared profile receiving or supplying dataframe state. |
| `arguments` | object | Resolved arguments passed to the function. Runtime storage placeholders remain unresolved. |
| `input_features` | array of strings | Features declared as inputs to the operation. |
| `output_features` | array of strings | Features produced by the operation. |
| `id_columns` | array of strings | Target profile grain keys, in declaration order. |
| `column_types` | object | Logical types for target keys and typed features, used by runtime validation. |
| `argument_types` | object | Declared argument types used for runtime binding. |
| `return_type` | string or null | Inspected implementation return annotation, when signature validation is enabled. |
| `package` | object or null | Installed distribution name and version for the entrypoint. |
| `dependency_ids` | array of strings | Identifiers of invocation prerequisites. |
| `row_context` | object or null | Input row-context requirement, when declared. |

Structural references in Spec are resolved to plan identifiers. Runtime
dataframe binding is deferred to the engine. The `@` profile reference denotes
the owning profile for the operation's declared inputs, not a completed frame.

## Stages

Each stage is a list of invocation identifiers. Every invocation appears exactly
once, and each dependency must appear in an earlier stage. Invocations in the
same stage are independent according to the declared dependency graph. An
engine may run them in parallel while preserving stage order.

## Dependencies

Operator inputs define the feature dependencies used to select and order
invocations. Ordinary argument values do not establish dependencies by
themselves. A plan limited to selected features also includes the features they
depend on, along with configured writes for the selected profiles. Those writes
may use features outside the selection.

The dependency graph must be acyclic. Plan loading checks invocation
identifiers, dependency references, and stage ordering. These structural
checks do not prove that dependencies inside function implementations are
declared or that calculations are correct. The engine must support the plan
version and declared backend.

## Compilation and plan validation

The compiler accepts a loaded Spec and validates it before compiling it into a
valid, schedulable plan. If you edit an already indexed Spec, reconstruct it with
`Spec.model_validate(document.model_dump())` first; resource views are cached.
Declaration rules are
defined in [Spec validation](spec.md#validation). Compilation checks
selected-feature feasibility, dependency ordering, plan schedulability, and
implementation entrypoints. Unless a function sets `validate_signature` to
`false`, it also checks keyword-call compatibility, required implementation
parameters, supported argument annotations, and any supported return
annotation against the declared contracts. Missing annotations are allowed;
known contradictions are not. Disabling signature validation does not disable
Spec checks. Execution still requires a loadable function.

Plan loading checks supported versions and valid root fields, invocation IDs,
dependency references, and stage ordering. The compiler owns operator expansion,
dependency resolution, feature selection, and scheduling. `ExecutionPlan`
validates that the compiler-supplied stages cover every invocation and preserve
dependency order; it does not choose or optimize the schedule. The Python
`Stage` model groups invocation IDs while the portable JSON representation
remains an array of arrays of strings.

## API migration and rebuilding plans

Load the Spec, compile it, and save the plan with `uptimely.plan`:

```python
from uptimely import compiler, plan as plan_io, spec

specification = spec.load_spec("spec.json")
compiled_plan = compiler.Compiler().compile(
    specification,
    features=["health_signal_normalized"],
)
plan_io.export_json(compiled_plan, "execution_plan.json")
restored = plan_io.from_json("execution_plan.json")
assert [invocation.id for invocation in restored.invocations] == [
    invocation.id for invocation in compiled_plan.invocations
]
```

Load a Spec with `uptimely.spec.load_spec` before passing it to `Compiler`.
Use `uptimely.plan` to read and write plans, and use
`ExecutionPlan.invocations` to access the planned steps. Do not rely on the
format of their IDs.

Plans earlier than version 9 are not supported.
Rebuild from the source Spec with `uptimely build PROJECT_ROOT`.
Plans lacking invocation runtime metadata (`id_columns`, `column_types`, and
`argument_types`) must likewise be rebuilt.

The engine returns results: `result.datasets` contains final profile frames,
`result.calculated_outputs` contains calculated features, and
`result.invocation_statuses` reports whether each planned step succeeded,
failed, or was skipped. `result.durations` and `result.failures` give more run
details.
