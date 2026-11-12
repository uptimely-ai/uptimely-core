# Spec vocabulary

These modules provide shared types used when describing and checking a Spec.
Most projects use the Python helpers in [Python authoring](python.md) instead.

## Operator labels

Uptimely derives a label from each operator's bindings and source and target
profiles. The labels describe the work; they are not set on the function.

| Label | Purpose |
| --- | --- |
| `read` | Load data into a profile. |
| `write` | Send data to an output. |
| `escape` | Run a function without producing a dataframe. |
| `conform` | Produce data at the same level as the target profile. |
| `expand` | Produce data at a more detailed level. |
| `collapse` | Produce data at a less detailed level. |
| `vectorize` | Add calculated values to the existing profile dataframe. |

For behavior and validation rules, see the
[Spec format reference](../architecture/spec.md).

::: uptimely.spec.operator_kinds
    options:
      heading_level: 2
      show_root_heading: false
      members:
        - OperatorKind
        - OperatorKindId
        - ReturnKind
        - DimensionChange
        - FragmentDimensions
        - RowCountRelation
        - KeyRelation
        - OPERATOR_KINDS
        - WRITE
        - READ
        - ESCAPE
        - CONFORM
        - EXPAND
        - COLLAPSE
        - VECTORIZE

## Argument types

`uptimely.spec.arg_types` defines argument types used in Spec documents.
Collections can be described with `array_of()` and `object_values_of()`.

::: uptimely.spec.arg_types
    options:
      heading_level: 2
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

## Reference selectors

`uptimely.spec.selectors` defines the strings used to refer to profiles,
features, dimensions, and row context in a Spec. For normal authoring, use the
helpers in [`up.ref`](python.md).

::: uptimely.spec.selectors
    options:
      heading_level: 2
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
