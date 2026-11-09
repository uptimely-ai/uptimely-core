# Spec validation

`uptimely.spec.validation` provides semantic validation and the structured
`SpecError` exception. Pydantic checks document shape and field types; semantic
validators check relationships between declarations. Independent return and
argument contracts are checked by their owning `FunctionTemplate` models;
binding positions require zero or one compute dataframe argument or exactly
two merge dataframe arguments. Slots are counted even when they reference the
same profile. Neither imports executable function implementations
or constructs compiler invocations.

The public [load_spec and from_python](api.md) helpers still validate
automatically by default. Pass `validate=False` to defer semantic validation
to the compiler or an explicit `validate_spec(document)` call. Structural
parsing remains mandatory. After editing declarations, call `document.rebuild()`
before validating or compiling so the model checks and cached views are fresh.

## Validation order

`validate_spec` runs checks in four fixed groups: references, declarations,
dependency cycles, then warnings. A failure stops validation immediately; warnings
are emitted only after all required checks pass. Function-template checks live
on `FunctionTemplate`, while the validation runner adds the corresponding spec
error code and document path.

Use the public runner for normal validation:

```python
from uptimely.spec.validation import validate_spec

validate_spec(document)
```

The runner is fail-fast and checks references before declarations and their
relationships, then checks dependency cycles. Profile features without
producers generate warnings only after these checks succeed. Individual rule
functions remain available for focused tests;
call them only when their required earlier checks have succeeded.

## Errors

Semantic failures raise `ValueError`; rules with structured diagnostics raise
its subclass `SpecError`. `SpecError.code` identifies the violated rule and
`SpecError.path` locates the declaration using mapping keys and sequence indexes.
An empty path identifies the document root. Messages are intended for people.
Pydantic reports document-shape errors separately.

## Organization and rule authoring

| Module in `uptimely.spec.validation` | Responsibility |
| --- | --- |
| `spec` | Ordered validation groups and fail-fast runner |
| `rules.profile_identity` | Profile identity and ordering checks |
| `rules.profiles` | Profile dimension membership |
| `rules.dimensions` | Parent references and ancestry cycles |
| `rules.features` | Feature ownership discovery and uniqueness |
| `rules.functions` | Run function-owned contract checks with spec diagnostics |
| `rules.bindings` | Supplied argument names and structural selector types |
| `rules.operators` | Operator declarations and iteration |
| `rules.operators.inputs` | Input feature scope, structural references, and source discovery |
| `rules.operators.outputs` | Output declarations, producers, and coverage warnings |
| `rules.operators.contracts` | Dataframe references and operator-specific relationships |
| `rules.operators.dependencies` | Operator feature dependency cycles |
| `rules.row_context` | Input ordering and context dimensions |
| `errors` | Structured validation errors |

Profile identity and ordering checks are implemented in `rules.profile_identity`.
Operator rules are grouped by the relationship they check, not by callable
metadata. Collapse shares input source discovery with every other operator;
only invariants specific to the derived collapse relationship are conditional
on that operator classification.

Rules access `spec.profile_items` and `spec.operator_items` directly when they need
ownership or diagnostic paths, and use `spec.profiles` or `spec.operators` otherwise.
The views contain the canonical models, not declaration wrappers.
`spec.feature_owners` retains every owner so ambiguous declarations can be
reported rather than selecting the first. Cached binding and dataframe views
centralize reference resolution while each rule checks its own invariant.

To add a rule:

1. Define a typed `validate_something(spec: Spec) -> None` function in the
   appropriate domain module. Check one invariant and raise on failure.
2. Reuse the owning resource's iteration and lookup helpers where needed.
   Keep rule-specific calculations local. Add the check to the appropriate
   ordered group in `uptimely.spec.validation.spec`.
3. Test valid inputs, a violation of the invariant, and that failures stop later
   groups.

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

## Profile identity and ordering

::: uptimely.spec.validation.rules.profile_identity
    options:
      heading_level: 3
      show_root_heading: false
      members: [validate_profile_ids]

</div>
