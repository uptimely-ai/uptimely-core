# Spec models

`uptimely.spec.model` defines the spec document structure, independent
of its authoring format. The [spec format reference](../../components/spec.md)
describes the document structure.

The compiler constructs executable invocations from these declarations.

## Resource indexes

The document model collects nested resources once, on the first index access.
Use `document.datasets["telemetry"]` or `document.features["pressure"]` instead
of walking entities and datasets. These dictionaries reference the original
declarations, not copies. Dataset dimension features are included in `features`;
the top-level dimension catalog remains `document.dimensions`.

`document.actions` is an ordered list of the original canonical `Action` objects.
Use `for action in document.actions` to traverse it. Action IDs are dataset-scoped,
so `document.actions_by_key` uses
`(entity_id, dataset_id, action_key)` keys. `document.arguments` contains function
argument declarations keyed by `(function_id, argument_key)`; bound values remain
on `action.binding.args`. `document.action_datasets` maps each action key to its
owning dataset occurrence.
`document.entrypoints` lists distinct function-catalog entrypoint strings in
declaration order without parsing them or importing implementations. Compilation
still parses and inspects only entrypoints needed by the selected graph.
`document.functions.iter_functions()` yields each function ID, its template, and
the number of arguments declared as dataframes.

When ownership matters, `dataset_items` contains `(dataset_key, dataset)` pairs
and `action_items` contains `(action_key, action)` pairs in declaration order.
Dataset keys are `(entity_id, dataset_id)`; action keys additionally contain the
action dictionary key. These lists retain duplicate occurrences and aliases for
validation without introducing additional Dataset or Action classes.
`datasets_by_key`, `feature_owners`, `feature_producers`, and
`actions_by_function` provide keyed lookups and relationships.
`feature_owners` excludes global
dimensions, which can occur in multiple datasets. ID-keyed indexes use the last
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
| `Entity` | `features`, `actions` keyed by `(dataset_id, action_key)`, `arguments` keyed by `(dataset_id, action_key, argument_name)`, `dimension_ids`, `dimension_id_set` |
| `Dataset` | `arguments` keyed by `(action_key, argument_name)`, `feature_producers`, `order_dimensions`, `order_references` |
| `Action` | `arguments`, `input_features`, `output_features`, `feature_selectors`, `dataset_references`, `dimensions_references`, `dimension_reference_paths` |
| `ActionFeatures` | `input_ids`, `output_ids` |
| `Binding` | `values_with_paths`, `references_by_prefix`, `dataset_input_references` |
| `FunctionTemplate` | `arguments_by_type` |
| `FunctionCatalog` | `arguments`, `functions_by_kind`, `by_kind(kind)` |

Raw child dictionaries such as `dataset.features`, `dataset.actions`, and
`function.args` remain available. Bound arguments are values; catalog arguments
are declarations. Feature and action references retain declaration order.

`action.dataset_references` contains normalized dataset IDs from nested binding
arguments, retaining duplicates and the current-dataset marker `@`. It reuses
the binding's cached traversal and does not require a Spec.
`action.feature_selectors` exposes normalized feature IDs from binding arguments,
including `@` and duplicates; it is separate from the explicitly declared
`action.input_features`.
`action.dimensions_references` likewise exposes normalized dimension IDs.
`action.dimension_reference_paths` additionally retains each reference's relative
binding argument path for diagnostics. Both reuse the same cached binding traversal.
`BindingArgumentResolver` resolves bound values for one invocation; dataset, feature,
and dimension-index context is configured once, then `resolve_arguments` receives
only the binding argument mapping.

Context-dependent views live on the Spec rather than wrapper objects:
`local_features` and `dimensions_by_dataset` use dataset keys;
`input_candidates`, `input_sources`, `actions_arguments`, `dataset_argument_sources`,
`dataset_argument_ids`, `dataset_argument_dimensions`, `matching_key_dimensions`, and
`binding_selectors` use action keys. Unresolved and ambiguous resources remain
visible to validators. `declaration_paths` preserves action dictionary keys for
binding diagnostics; `action_paths` preserves model IDs for contract diagnostics.
`get_row_context_dataset(action_key)` returns the dataset whose observations the
action's context describes, and `get_row_context_dimensions(action_key)` returns
its entity's dimension IDs. Dimension-removing operations use the inferred source;
other operations use the target. Both return `None` for an unresolved source.
Row context itself remains available directly as `action.row_context`.
`Binding.dataset_input_references` contains ordered dataset data references,
retaining duplicates and `@` while excluding identifier and dimension-list selectors.
`binding_selectors_with_paths` flattens `binding_selectors` into ordered
`(binding_args_path, value, argument_type)` tuples for validation. These paths
identify the action's binding argument collection, not individual nested leaves.

<div class="api-reference" markdown="1">

## spec

`uptimely.spec.model.spec` defines the root spec document.

::: uptimely.spec.model.spec
    options:
      heading_level: 3
      show_root_heading: false
      members: [Spec, SPEC_VERSION]

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

## dataset

`uptimely.spec.model.dataset` defines entities, datasets, features, and
their relationships.

`Entity.datasets` is a dictionary keyed by dataset ID. Access a dataset with
`document.entities["pump"].datasets["telemetry"]`, or iterate over
`entity.datasets.values()`. The internal `Dataset.id` is derived from the JSON
object key and excluded from serialized dataset attributes. `Dataset.name` is an
optional human-readable display name, independent of that identifier.

::: uptimely.spec.model.dataset
    options:
      heading_level: 3
      show_root_heading: false
      members: [Entity, Dataset, Feature, Order, RowScope, Action, ActionFeatures]

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
