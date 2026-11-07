# Spec models

`uptimely.spec.model` defines the spec document structure, independent
of its authoring format. The [spec format reference](../../components/spec.md)
describes the document structure.

The compiler constructs executable invocations from these declarations.

## Derived views

The document caches commonly used views of profiles, features, operators, and
arguments when first accessed. Use `document.profiles["telemetry"]` or
`document.features["pressure"]` rather than repeatedly traversing the document.
These dictionaries reference the original declarations, not copies. Selected
grain-key features are included in `features`; the top-level dimension catalog
remains `document.dimensions`, where each dimension exposes its resolutions.
Use `document.grain_keys_by_profile` and
`document.grain_key_types_by_profile` for the dataframe keys and types selected
by each profile.

`document.operators` is an ordered list of the original canonical `Operator` objects.
Use `for operator in document.operators` to traverse it. Operator IDs are profile-scoped,
so `document.operators_by_key` uses `(profile_id, operator_key)` keys.
`document.arguments` contains function
argument declarations keyed by `(function_id, argument_key)`; bound `BindingArgument`
objects remain on `operator.compute.args`. `document.operator_profiles` maps each operator key to its
owning profile.
`document.entrypoints` lists distinct function-catalog entrypoint strings in
declaration order without parsing them or importing implementations. Compilation
still parses and inspects only entrypoints needed by the selected graph.
`document.functions.iter_functions()` yields each function ID, its template, and
the number of arguments declared as dataframes.

When ownership matters, `profile_items` contains `(profile_key, profile)` pairs
and `operator_items` contains `(operator_key, operator)` pairs in declaration order.
Operator keys contain the profile ID and assembly dictionary key. The operator list
retains aliases for validation without introducing additional Operator classes.
`profiles_by_key`, `feature_owners`, `feature_producers`, and
`operators_by_function` provide keyed lookups and relationships.
`feature_owners` excludes global
dimensions, which can occur in multiple profiles. ID-keyed views use the last
declaration when IDs collide; validate a document before relying on unique ownership.

Views use `functools.cached_property`; treat declarations and cached collections
as read-only once accessed. Loading and compilation validate the document and
can warm these caches. After editing declarations, use `document.rebuild()` and
then validate or compile the returned document. This reconstructs the spec from
its serialized fields and starts with fresh cached views. `model_copy(update=...)`
can retain warmed caches and is not a cache-reset mechanism. Cached views are not
serialized to JSON.

### Nested model views

Nested models also expose reusable views, so callers do not need to flatten or
normalize their children:

| Model | Views |
| --- | --- |
| `Profile` | `all_features`, `arguments` keyed by `(operator_key, argument_name)`, `feature_producers`, `dimension_ids`, `dimension_id_set`, `order_dimensions`, `order_references` |
| `Operator` | `bindings`, `arguments`, `input_features`, `output_features`, `feature_selectors`, `profile_references`, `dimensions_references`, `dimension_reference_paths` |
| `Interface` | `input_ids`, `output_ids` |
| `Binding` | `values_with_paths`, `references_by_prefix`, `metadata_references_with_paths`, `grain_references_with_paths`, `feature_references`, `uses_current_feature`, `profile_dataframe_references` |
| `BindingArgument` | `root`, `children`, `leaves_with_paths`, `references_with_paths`, `prefix`, `identifier`, `selector`, `selector_value_type`, `is_current_profile_dataframe`, `is_current_fragment`, `is_current_feature_reference`, `is_grain_reference`, `profile_dataframe_references`, `inferred_feature_inputs` |
| `FunctionTemplate` | `arguments_by_type` |
| `FunctionCatalog` | `arguments`, `functions_by_kind`, `by_kind(kind)` |

`FunctionTemplate` owns checks for its return kind, dataframe argument count,
and argument contracts. Semantic validation runs these checks on the function
models. Rebuild an edited Spec before validating it again so all cached views
reflect the edits.

Raw child dictionaries such as `profile.features`, `profile.assembly`, and
`function.args` remain available. Bound arguments wrap values; catalog arguments
are declarations. Feature and operator references retain declaration order.

`operator.profile_references` contains normalized profile IDs from nested binding
arguments, retaining duplicates and the current-profile marker `@`. It reuses
the binding's cached traversal and does not require a Spec.
`operator.feature_selectors` exposes normalized feature IDs from compute
binding arguments, including `@` and duplicates. Merge bindings do not accept
feature references; joins use dimension keys instead.
`operator.dimensions_references` likewise exposes normalized dimension IDs.
`operator.dimension_reference_paths` additionally retains each reference's relative
binding argument path for diagnostics. Both reuse the same cached binding traversal.
Each `BindingArgument` owns its nested traversal, parsed selectors, inferred data
dependencies, argument-type propagation, and value resolution from explicit
invocation context. `Binding` stores `function` and `args`, aggregates argument
views, and resolves its argument mapping. `Operator.resolve_args` selects the
compute or merge binding and supplies its output-feature context.

`operator.bindings` contains compute and any merge binding in that order.
Traverse `document.operators` for operator objects, or `document.operator_items`
when declaration keys are needed for diagnostics. Access `operator.compute` or
`operator.merge` directly for role-specific checks; use `operator.bindings.items()`
for checks applying to both. Resolve each binding's function ID through the
function catalog. Diagnostic paths describe locations only; they do not encode
binding roles or profile context for consumers to extract.

`binding.argument_mismatches(function)` returns `(missing_names, unknown_names)`
sets. `binding.typed_arguments(function)` yields scalar argument objects and their
declared types, propagating container types and skipping undeclared arguments.
`argument.selector_value_type` exposes a selector's required value type;
`argument.required_type(declared_type)` additionally preserves nullable profile
dataframe arguments. These methods use the supplied function contract rather than
attaching catalog or Spec state to a binding.

### Working with bound arguments

`binding.args` now maps names to `BindingArgument` objects instead of raw values.
Constructing or loading a `Binding` wraps supplied JSON values automatically.
Read an argument's value with `binding.args["column"].root`; use
`binding.model_dump()["args"]` to obtain the complete raw argument mapping.
Arguments serialize directly as their values, so the spec JSON shape is unchanged.
Pydantic values supplied inside an argument are converted to document values;
other non-JSON values are rejected.

When editing a binding in Python, insert argument objects:

```python
from uptimely.spec import model

binding = model.Binding(function="calculate", args={"column": "$features.pressure"})
binding.args["column"] = model.BindingArgument("$features.temperature")
resolved = binding.resolve_args("telemetry")
```

`argument.resolve(context)` resolves nested structural references without changing
the supplied values. `binding.resolve_args(...)` resolves all arguments and accepts
profile ID, output-feature ID, grain keys, and optional resource metadata. Context
is never cached on an argument: the same binding can be resolved for different
profiles and output features.

Python authoring infers omitted interface inputs from bare feature references,
including their string forms, but excludes metadata selectors, the current-output
marker, and declared outputs. An explicit interface, including `inputs=[]`, always
overrides inference. Profile dependencies are inferred from dataframe
references, not from grain keys or descriptive metadata.

Context-dependent views live on the Spec rather than wrapper objects:
`dimensions_by_profile` uses profile keys;
`input_candidates`, `input_sources`, `operator_dataframe_arguments`, `dataframe_argument_profiles`,
`dataframe_argument_profile_ids`, `dataframe_argument_grain_keys`, and `matching_profile_keys`
use operator keys. Unresolved and ambiguous resources remain
visible to validators. `declaration_paths` preserves operator dictionary keys for
binding diagnostics; `operator_paths` preserves model IDs for contract diagnostics.
`get_row_context_profile(operator_key)` returns the profile whose observations the
operator's context describes, and `get_row_context_dimensions(operator_key)` returns
its dimension IDs. Dimension-removing operations use the inferred source;
other operations use the target. Both return `None` for an unresolved source.
Row context itself remains available directly as `operator.row_context`.
`Binding.profile_dataframe_references` contains ordered profile dataframe references,
retaining duplicates and `@` while excluding identifier and dimension-list selectors.
`binding_arguments_with_paths` returns ordered
`(binding_args_path, argument, argument_type)` tuples for validation, deriving each
leaf's type from its function argument. The existing `binding_selectors_with_paths`
view supplies raw values instead of argument objects. These paths identify the
operator's binding argument collection, not individual nested leaves; metadata
reference views retain individual leaf paths for precise diagnostics.

<div class="api-reference" markdown="1">

## spec

`uptimely.spec.model.spec` defines the root spec document.

::: uptimely.spec.model.spec
    options:
      heading_level: 3
      show_root_heading: false
      members: [Spec, SpecSource, SPEC_VERSION]

## base

`uptimely.spec.model.base` defines the strict document-model contract and display
naming policy.

::: uptimely.spec.model.base
    options:
      heading_level: 3
      show_root_heading: false
      members: [StrictModel]

## dimension

`uptimely.spec.model.dimension` defines observation dimensions and their keyed
resolutions.

::: uptimely.spec.model.dimension
    options:
      heading_level: 3
      show_root_heading: false
      members: [Dimension, Resolution]

## binding_argument

`uptimely.spec.model.binding_argument` owns bound values and invocation-specific
selector resolution.

::: uptimely.spec.model.binding_argument
    options:
      heading_level: 3
      show_root_heading: false
      members: [BindingArgument]

## binding

`uptimely.spec.model.binding` defines function bindings and aggregate argument views.

::: uptimely.spec.model.binding
    options:
      heading_level: 3
      show_root_heading: false
      members: [Binding]

## profile

`uptimely.spec.model.profile` defines profiles, features, operators, and
their relationships. Profiles are keyed by ID in the top-level `profiles`
mapping, and their internal IDs are excluded from serialized profile attributes.

::: uptimely.spec.model.profile
    options:
      heading_level: 3
      show_root_heading: false
      members: [Profile, Feature, Order, Operator, Interface]

## functions

`uptimely.spec.model.functions` defines reusable function metadata and the
function catalog.

::: uptimely.spec.model.functions
    options:
      heading_level: 3
      show_root_heading: false
      members: [Argument, FunctionTemplate, FunctionCatalog]

For supported function kinds and values, see the
[spec vocabulary](../spec-vocabulary.md).

</div>
