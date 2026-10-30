# Spec vocabulary

These modules define the spec's shared function-kind, argument-type, and reference
vocabulary. Components that author, validate, compile, or execute specs use the
same definitions.

<div class="api-reference" markdown="1">

## Function kinds

`uptimely.spec.functions` defines immutable function-kind contracts and their
string identifiers. `FUNCTION_KINDS` is a read-only mapping from each supported
identifier to its contract.

The built-in structural policies are independent. `dimension_change` compares
the bound source dataset's declared dimension identities with the target
dataset's declared identities during spec validation: `preserve` requires equal
sets, `add` requires the target to be a strict superset, and `remove` requires
the target to be a strict subset. `fragment_dimensions` checks the raw
materialized result against the target entity's dimensions: `target` requires
all target dimension columns; `subset` permits any subset and leaves the
engine to assemble it against the accumulated target. `row_count_relation`
compares the raw result's row count with the accumulated target frame.
`key_relation` independently compares dimension-key identities, ignoring row
order. These policies never infer row-count or key guarantees from a
dimensional change.

| Kind | Source-to-target dimensions (spec validation) | Raw result dimensions (runtime) | Row-count reference (runtime) | Key-identity reference (runtime) |
| --- | --- | --- | --- | --- |
| `read` | Unrestricted; no bound source | All target dimensions | Unrestricted | Unrestricted |
| `write` | Unrestricted | Not applicable; no dataframe result | Unrestricted | Unrestricted |
| `escape` | Unrestricted | Not applicable; its return is ignored | Unrestricted | Unrestricted |
| `conform` | Preserve: bound foreign source to target | All target dimensions | Unrestricted; source may have a different row scope | Unrestricted |
| `expand` | Add: bound lower-dimensional source to target | Any subset of target dimensions; assemble against accumulated target | Unrestricted | Unrestricted |
| `collapse` | Remove: bound higher-dimensional source to target | All target dimensions | Unrestricted | Unrestricted |
| `vectorize` | Preserve: bound target dataset to target | All target dimensions | Same row count as accumulated target | Identical keys to accumulated target, regardless of row order |

Dimensionless materialized datasets and fragments have a separate structural
limit of at most one row. This is not a same-row-count guarantee. Expand's
partial raw fragment is validated before broadcasting; its assembled result
uses the accumulated target's complete dimensions. Conform and expand do not
assume their foreign source has the target's rows. Feature dependencies and
explicit dataframe arguments remain distinct: a logical output does not
materialize an ignored return value.

::: uptimely.spec.functions
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - FunctionKind
        - FunctionKindId
        - ReturnKind
        - DimensionChange
        - FragmentDimensions
        - RowCountRelation
        - KeyRelation
        - FUNCTION_KINDS
        - WRITE
        - READ
        - ESCAPE
        - CONFORM
        - EXPAND
        - COLLAPSE
        - VECTORIZE

## Argument types

`uptimely.spec.arg_types` defines atomic argument types and helpers for the
recursive collection expressions `array[item_type]` and `object{str: value_type}`.

::: uptimely.spec.arg_types
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - AtomicArgumentType
        - ATOMIC_ARGUMENT_TYPES
        - DATAFRAME
        - STRING
        - INTEGER
        - FLOAT
        - BOOLEAN
        - ARRAY
        - OBJECT
        - array_of
        - object_values_of
        - array_item_type
        - object_value_type

## Reference syntax

`uptimely.spec.selectors` defines dataset, feature, and dimension reference
prefixes, the current-dataset marker, and selectors for identifiers and dataframes.

::: uptimely.spec.selectors
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - FEATURE_PREFIX
        - DATASET_PREFIX
        - DIMENSION_PREFIX
        - STRUCTURAL_PREFIXES
        - CURRENT_ID
        - ID_SELECTOR
        - DATAFRAME_SELECTOR

</div>
