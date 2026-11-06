# Spec models

`uptimely.spec.model` defines the spec document structure, independent
of its authoring format. The [spec format reference](../../components/spec.md)
describes the document structure.

The compiler constructs executable invocations from these declarations.

## Resource indexes

The document model indexes profiles, features, operators, and arguments once, on
the first index access. Use `document.profiles["telemetry"]` or
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
argument declarations keyed by `(function_id, argument_key)`; bound values remain
on `operator.compute.args`. `document.operator_profiles` maps each operator key to its
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
dimensions, which can occur in multiple profiles. ID-keyed indexes use the last
declaration when IDs collide; validate a document before relying on unique ownership.

Views use `functools.cached_property`; treat declarations and cached collections
as read-only once accessed. Loading and compilation validate the document and
can warm these caches. After edits, construct a new document with
`Spec.model_validate(document.model_dump())` before reading or validating it.
`model_copy(update=...)` can retain warmed caches and is not a cache-reset
mechanism. Cached views are not serialized to JSON.

### Nested model views

Nested models also expose reusable views, so callers do not need to flatten or
normalize their children:

| Model | Views |
| --- | --- |
| `Profile` | `all_features`, `arguments` keyed by `(operator_key, argument_name)`, `feature_producers`, `dimension_ids`, `dimension_id_set`, `order_dimensions`, `order_references` |
| `Operator` | `arguments`, `input_features`, `output_features`, `feature_selectors`, `dataset_references`, `dimensions_references`, `dimension_reference_paths` |
| `Interface` | `input_ids`, `output_ids` |
| `Binding` | `values_with_paths`, `references_by_prefix`, `dataset_input_references` |
| `FunctionTemplate` | `arguments_by_type` |
| `FunctionCatalog` | `arguments`, `functions_by_kind`, `by_kind(kind)` |

Raw child dictionaries such as `profile.features`, `profile.assembly`, and
`function.args` remain available. Bound arguments are values; catalog arguments
are declarations. Feature and operator references retain declaration order.

`operator.dataset_references` contains normalized profile IDs from nested binding
arguments, retaining duplicates and the current-profile marker `@`. It reuses
the binding's cached traversal and does not require a Spec.
`operator.feature_selectors` exposes normalized feature IDs from compute
binding arguments, including `@` and duplicates. Merge bindings do not accept
feature references; joins use dimension keys instead.
`operator.dimensions_references` likewise exposes normalized dimension IDs.
`operator.dimension_reference_paths` additionally retains each reference's relative
binding argument path for diagnostics. Both reuse the same cached binding traversal.
`BindingArgumentResolver` resolves bound values for one invocation; profile-dataframe,
feature, and dimension-index context is configured once, then `resolve_arguments` receives
only the binding argument mapping.

Context-dependent views live on the Spec rather than wrapper objects:
`dimensions_by_profile` uses profile keys;
`input_candidates`, `input_sources`, `operator_arguments`, `dataset_argument_sources`,
`dataset_argument_ids`, `dataset_argument_grain_keys`, and `matching_profile_keys`
use operator keys. Unresolved and ambiguous resources remain
visible to validators. `declaration_paths` preserves operator dictionary keys for
binding diagnostics; `operator_paths` preserves model IDs for contract diagnostics.
`get_row_context_profile(operator_key)` returns the profile whose observations the
operator's context describes, and `get_row_context_dimensions(operator_key)` returns
its dimension IDs. Dimension-removing operations use the inferred source;
other operations use the target. Both return `None` for an unresolved source.
Row context itself remains available directly as `operator.row_context`.
`Binding.dataset_input_references` contains ordered profile dataframe references,
retaining duplicates and `@` while excluding identifier and dimension-list selectors.
`binding_selectors_with_paths` returns ordered
`(binding_args_path, value, argument_type)` tuples for validation, deriving each
selector's type from its function argument. These paths identify the operator's
binding argument collection, not individual nested leaves.

<div class="api-reference" markdown="1">

## spec

`uptimely.spec.model.spec` defines the root spec document.

::: uptimely.spec.model.spec
    options:
      heading_level: 3
      show_root_heading: false
      members: [Spec, Options, SPEC_VERSION]

## common

`uptimely.spec.model.common` defines shared dimensions, arguments, and
bindings.

::: uptimely.spec.model.common
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - StrictModel
        - SpecSource
        - Dimension
        - Argument
        - BindingArgument
        - Binding
        - BindingArgumentResolver

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
      members: [FunctionTemplate, FunctionCatalog]

For supported function kinds and values, see the
[spec vocabulary](../spec-vocabulary.md).

</div>
