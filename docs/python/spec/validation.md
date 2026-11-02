# Spec validation

`uptimely.spec.validation` provides semantic validation and the structured
`SpecError` exception. Pydantic checks document shape and field types; semantic
validators check relationships between declarations. Neither imports executable
function implementations or constructs compiler invocations.

The public [load_spec and from_python](api.md) helpers still validate
automatically by default. Pass `validate=False` to defer semantic validation
to the compiler or an explicit `validate_spec(document)` call. Structural
parsing remains mandatory. Call `validate_spec(document)` again after editing
a model.

## Flat atomic rules

Every semantic validator accepts the same spec document and returns `None` on
success or raises `ValueError` on failure. Each checks one invariant across the
document, not a phase containing several different checks:

```python
from uptimely.spec import model
from uptimely.spec.validation.rules import dimensions, entities

document = model.Spec.model_validate(raw_document)

dimensions.validate_parent(document)
dimensions.validate_parent_cycle(document)
entities.validate_entity_dimensions(document)
```

Rules do not call other validators, mutate the document, or save state for later
rules. Rules reuse the models' cached resource and reference views; there is no
separate validation context. After editing an already indexed document, construct
a new Spec from its serialized fields before validating it. See
[resource indexes](model.md#resource-indexes).

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
| `rules.datasets` | Dataset declarations, iteration, identity, and ordering |
| `rules.dimensions` | Parent references and ancestry cycles |
| `rules.entities` | Entity dimension membership |
| `rules.features` | Feature ownership discovery and uniqueness |
| `rules.functions` | Function return and dataframe argument contracts |
| `rules.bindings` | Supplied argument names and structural selector types |
| `rules.actions` | Action declarations and iteration |
| `rules.actions.inputs` | Input feature scope, structural references, and source discovery |
| `rules.actions.outputs` | Output declarations, producers, and coverage warnings |
| `rules.actions.contracts` | Dataframe references and kind-specific relationships |
| `rules.actions.dependencies` | Action feature dependency cycles |
| `rules.row_context` | Input ordering and context dimensions |
| `errors` | Structured validation errors |

Resource modules use the plural names of the spec collections. Action rules are
grouped by the relationship they check, not by function kind. Collapse shares
input source discovery with every other action; only invariants specific to
collapsing are conditional on that kind.

Rules access `spec.dataset_items` and `spec.action_items` directly when they need
ownership or diagnostic paths, and use `spec.datasets` or `spec.actions` otherwise.
The indexed values are the canonical models, not declaration wrappers.
`spec.feature_owners` retains every owner so ambiguous declarations can be
reported rather than selecting the first. Cached binding and dataframe views
centralize reference resolution while each rule checks its own invariant.

To add a rule:

1. Define a typed `validate_something(spec: Spec) -> None` function in the
   appropriate domain module. Check one invariant and raise on failure.
2. Reuse the owning resource's iteration and lookup helpers where needed.
   Keep rule-specific calculations local;
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

## datasets

::: uptimely.spec.validation.rules.datasets
    options:
      heading_level: 3
      show_root_heading: false
      members: [validate_dataset_ids]

</div>
