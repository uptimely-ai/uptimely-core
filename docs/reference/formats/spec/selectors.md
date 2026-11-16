# Spec: Selectors

## Selectors

Selectors let a field refer to a declared resource, one of its attributes, or
a runtime value. Use them only in fields marked `Yes` in the `Selector` column
of the schema tables. For object and array fields, a selector may appear inside
the value.

Some fields use a selector to identify a resource directly. For example,
`interface.inputs` and `interface.outputs` use feature selectors such as
`$features.temperature_mean`, while `row_context.dimension` uses a dimension
selector such as `$dimensions.measurement_time`. Other fields require a plain
identifier or a structured value instead. For example, `compute.function`
takes a function ID, and `grain` uses a `dimension` and `resolution` pair.

### Function argument selectors

Function arguments can use these structural selectors:

| Argument reference | Argument type | Value passed to the function |
| --- | --- | --- |
| `$features.<id>.id` | `string` | Feature identifier string. |
| `$dimensions.<id>.id` | `string` | Dimension identifier string. |
| `$dimensions.<id>.resolutions.<resolution_id>.id` | `string` | Resolution identifier string. |
| `$dimensions.<id>.resolutions.<resolution_id>.key` | `string` | Dataframe key declared for that resolution. |
| `$dimensions.<id>.resolutions.<resolution_id>.type` | `string` | Declared type of that key. |
| `$dimensions.<id>.resolutions.<resolution_id>.parent` | `string` | Parent resolution ID, or `null` when no parent is declared. |
| `$profiles.<id>.grain.ids` | `array[string]` | Dataframe key names selected by that profile's grain. |
| `$profiles.@.grain.ids` | `array[string]` | Dataframe key names selected by the operator's target profile. |
| `$profiles.<id>.dataset` | `dataframe` | Dataframe for that profile. |
| `$profiles.@.dataset` | `dataframe` | Dataframe for the current target profile. |
| `$profiles.<id>.id` | `string` | Profile identifier string. |
| `$features.@.id` | `string` | The operator's feature output ID when it declares exactly one output. |
| `$operators.@.fragment` | `dataframe` | Fragment produced by the compute function for the merge function. |

Use `$profiles.@.dataset` as the merge dataset and `$operators.@.fragment` as
the merge fragment. The fragment selector is accepted only in `merge.args`.

Use the declared argument type that matches the selected value. For example,
`.id` requires `string`, `.dataset` requires `dataframe` (or `dataframe | null`
for the initial merge dataset), and grain-key selectors require
`array[string]`. Grain keys must be selected by the target profile and every
profile whose dataframe is passed to the function. The `.parent` selector must
be declared as `string` and names a resolution in the same dimension, though
it resolves to `null` when no parent is set.

The `@` marker refers to the current target profile in `$profiles.@` and the
current operator in `$features.@` or `$operators.@`. `$features.@.id` is only
available when the operator declares exactly one output.

Compute arguments can also use feature metadata, such as
`$features.<id>.name`. Function arguments can select other resource metadata,
such as `$profiles.<id>.category`, and the current operator's row context
through `$operators.@.row_context.dimension`,
`$operators.@.row_context.before`, and `$operators.@.row_context.after`.
Compute and merge arguments can select runtime values with `$params.<name>` and
`$paths.<name>`. These values come from project runtime configuration and are
resolved during execution. Merge arguments cannot reference features.

Selecting a dimension or resolution does not pass its dataframe key
automatically. Use a key selector or pass the selected dataset keys as an
explicit argument when the function needs them, such as for grouping or
matching rows across dimensions.

## Validation

Spec validation checks the version, field types, required values, and rejects
unknown fields. It checks structural references against declared resources,
function arguments and return rules against their operator roles, row context
against input dimensions and order, and feature requirements for cycles. Each
non-dimension feature may have at most one producer. Declare `returns: "any"`
when the function's result is intentionally ignored. Outputs from a workflow
operator satisfy feature requirements during validation, but the engine does
not create their data. A workflow has no dataframe inputs, dataframe output, or
merge, and its result is ignored. Its feature inputs and outputs declare logical
dependencies and are not dataframe values passed to or produced by the engine.
Selected plans include workflows belonging to profiles of requested features.
A declared feature with no producing operator causes a
warning, but does not prevent the Spec from loading. Spec validation does not
import implementations or inspect calculated data. Parameter and path
references are resolved from project configuration during execution.

Compilation checks whether the declared workflow can be run for the selected
profiles. During execution, the engine always checks dataframe types and
required columns. When run validation is enabled with `uptimely run --validate`
or `Engine.run(validate=True)`, it also checks input-feature availability, key
uniqueness, preservation rules, and declared column types.

The built-in engine currently accepts Polars `DataFrame` and `LazyFrame`
values only. It does not accept other dataframe types or custom adapters.
