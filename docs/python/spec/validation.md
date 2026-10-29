# Spec validation

`uptimely.spec.validation` provides semantic validation and the structured
`SpecError` exception. Pydantic checks document shape and field types; semantic
validators check relationships between declarations. Neither imports executable
function implementations or constructs compiler invocations.

The public [load_spec and from_python](api.md) helpers still validate
automatically. Call `validate_spec(document)` again after editing a model.

## Flat atomic rules

Every semantic validator accepts the same spec document and returns `None` on
success or raises `ValueError` on failure. Each checks one invariant across the
document, not a phase containing several different checks:

```python
from uptimely.spec import model
from uptimely.spec.validation import dimensions

document = model.Spec.model_validate(raw_document)

dimensions.validate_parent(document)
dimensions.validate_parent_cycle(document)
dimensions.validate_entity_dimensions(document)
```

Rules do not call other validators, mutate the document, or save state for later
rules. Small traversal and reference-resolution helpers are shared where useful;
there is no shared validation context or attached cache. Revalidating a document
always observes its current declarations.

Direct calls are useful for individual checks, but the caller must first satisfy
their prerequisites. For normal whole-document validation, use the dependency
runner instead:

```python
from uptimely.spec.validation import validate_spec

validate_spec(document)
```

## Explicit dependencies

`VALIDATION_DEPENDENCIES` in `uptimely.spec.validation.spec` maps each validator
to the validators that must succeed before it runs. The graph contains functions,
not rule names or phase objects. For example:

```python
VALIDATION_DEPENDENCIES = {
    dimensions.validate_parent: (),
    dimensions.validate_parent_cycle: (dimensions.validate_parent,),
}
```

The runner uses Python's `graphlib.TopologicalSorter` to determine the execution
order. It verifies the dependency graph is acyclic before calling any rule.
Shared prerequisites run once per validation call. All validators receive the
same document.

Validation is fail-fast: if a prerequisite raises, execution stops immediately.
No dependent check runs on invalid prerequisites, and there is no aggregation,
fallback owner, or automatic retry. A cycle between validators raises
`graphlib.CycleError`, indicating a programming/configuration error rather than
a cycle inside the spec.

Independent rules have a deterministic order based on the dependency mapping's
insertion order. Historical first-error precedence is not preserved. Declare
every actual prerequisite instead of relying on incidental ordering.

Dataset features without producers generate warnings only after all validators
have succeeded.

## Errors

Semantic failures raise `ValueError`; rules with structured diagnostics raise
its subclass `SpecError`. `SpecError.code` identifies the violated rule and
`SpecError.path` locates the declaration using mapping keys and sequence indexes.
An empty path identifies the document root. Messages are intended for people.
Pydantic reports document-shape errors separately.

## Organization and rule authoring

| Module in `uptimely.spec.validation` | Responsibility |
| --- | --- |
| `spec` | Dependency mapping and fail-fast topological runner |
| `traversal` | Read-only dataset/action iteration and local lookup helpers |
| `dataset` | Dataset identity and ordering |
| `dimensions` | Parent references, ancestry cycles, and entity dimensions |
| `functions` | Function return and dataframe argument contracts |
| `bindings` | Supplied argument names and structural selector types |
| `action_outputs` | Output declarations, ownership, producers, and coverage warnings |
| `action_inputs` | Input feature scope and structural references |
| `collapse_inputs` | Collapse source discovery and source scope |
| `row_context` | Input ordering and context dimensions |
| `action_contracts` | Dataframe references and kind-specific relationships |
| `dependencies` | Action feature dependency cycles |
| `errors` | Structured validation errors |

To add a rule:

1. Define a typed `validate_something(spec: Spec) -> None` function in the
   appropriate domain module. Check one invariant and raise on failure.
2. Reuse traversal helpers where needed. Keep rule-specific calculations local;
   do not introduce a context, validation registry decorator, or phase hierarchy.
3. Add the function to `VALIDATION_DEPENDENCIES`, listing its prerequisites.
   Document any assumptions needed by callers invoking the function directly.
4. Test valid inputs, a violation of the invariant, and dependency behavior.
   The flat-validation contract tests also verify every rule is registered.

The compiler separately checks executable signatures, selected-plan feasibility,
and invocation dependency ordering.

<div class="api-reference" markdown="1">

## errors

::: uptimely.spec.validation.errors
    options:
      heading_level: 3
      show_root_heading: false
      members: [SpecError]

## spec

::: uptimely.spec.validation.spec
    options:
      heading_level: 3
      show_root_heading: false
      members: [validate_spec]

## dataset

::: uptimely.spec.validation.dataset
    options:
      heading_level: 3
      show_root_heading: false
      members: [validate_dataset_ids]

</div>
