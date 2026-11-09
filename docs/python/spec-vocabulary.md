# Spec vocabulary

These modules define the spec's shared function-kind, argument-type, and reference
vocabulary. Components that author, validate, compile, or execute specs use the
same definitions.

<div class="api-reference" markdown="1">

## Function kinds

`uptimely.spec.function_kinds` defines immutable function-kind contracts and their
string identifiers. `FUNCTION_KINDS` is a read-only mapping from each supported
identifier to its contract. `produces_fragment` distinguishes assembled
contributions from `vectorize`, which returns a complete enriched target frame.

The built-in structural policies are independent. `dimension_change` compares
the bound source profile's selected dimensional identities with the target
profile's selected identities during spec validation: `preserve` requires equal
sets, `add` requires the target to be a strict superset, and `remove` requires
the target to be a strict subset. `fragment_dimensions` checks the raw
materialized fragment against the target profile grain: `target` requires all
target grain keys; `subset` permits any subset and leaves the engine to assemble
it against the accumulated target. For fragment-producing kinds,
`row_count_relation` compares the raw result's row count with the accumulated
target and `key_relation` compares key identities. Vectorize does not produce a
fragment: it must return all existing target columns plus its declared outputs.
With `validate=True`, the engine also checks its `row_order_relation` and
`existing_data_relation` contracts by comparing old columns and values in their
original row order. These policies never infer row-count or key guarantees
from a dimensional change.

| Kind | Source-to-target dimensions (spec validation) | Dataframe result (runtime) |
| --- | --- | --- |
| `read` | Unrestricted; no bound source | Target-grain fragment |
| `write` | Unrestricted | Not applicable; no dataframe result |
| `escape` | Unrestricted | Not applicable; its return is ignored |
| `conform` | Preserve: bound foreign source to target | Target-grain fragment |
| `expand` | Add: bound lower-dimensional source to target | Partial-grain fragment assembled against the target |
| `collapse` | Remove: bound higher-dimensional source to target | Target-grain fragment |
| `vectorize` | Preserve: bound target profile to target | Complete enriched target frame; no fragment or join |

Dimensionless profile frames and fragments have a separate structural
limit of at most one row. This is not a same-row-count guarantee. Expand's
partial raw fragment is validated before broadcasting; its assembled result
uses the accumulated target's complete dimensions. Conform and expand do not
assume their foreign source has the target's rows. Feature dependencies and
explicit dataframe arguments remain distinct: a logical output does not
materialize an ignored return value.

::: uptimely.spec.function_kinds
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

`uptimely.spec.selectors` defines profile, feature, dimension, and operator
reference prefixes, the current-resource marker, and selectors for identifiers,
profile grain keys, datasets, and current-operator row-context attributes.

::: uptimely.spec.selectors
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - REFERENCE_PREFIX
        - FEATURE_PREFIX
        - PROFILE_PREFIX
        - PROFILE_GRAIN_IDS_SELECTOR
        - DIMENSION_PREFIX
        - OPERATOR_PREFIX
        - ROW_CONTEXT_PREFIX
        - ROW_CONTEXT_ATTRIBUTES
        - STRUCTURAL_PREFIXES
        - CURRENT_ID
        - ID_SELECTOR
        - DATASET_SELECTOR

</div>
