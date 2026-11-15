# Spec vocabulary

These modules provide shared types used when describing and checking a Spec.
Most projects use the Python helpers in [Python authoring](python.md) instead.

## Operator bindings

`OPERATOR_BINDINGS` describes the dataframe contract of each primary binding
and the additional `merge` binding. Logical feature inputs and outputs are
declared independently.

::: uptimely.spec.operator_bindings
    options:
      heading_level: 2
      show_root_heading: false
      members:
        - BindingContract
        - BindingKind
        - PrimaryBindingKind
        - OPERATOR_BINDINGS

## Derived grain relationships

Explorer reports source-to-target relationships inferred from profile grains
and their dimension hierarchies. These values are not stored in the Spec or
portable execution plan.

The values are `same`, `expand`, `collapse`, `unrelated`, and
`not_applicable`. For the execution contracts that remain in a plan, see the
[Spec format reference](../../architecture/spec.md).

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
