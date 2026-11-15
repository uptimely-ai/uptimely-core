# Spec vocabulary

These modules provide shared types used when describing and checking a Spec.
Most projects use the Python helpers in [Python authoring](python.md) instead.

## Operator bindings

`OPERATOR_BINDINGS` describes the required `compute` binding and the optional
`merge` binding. Dataframe counts are independent of logical feature dependencies.

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

An absent source profile is reported as `emerge`, while an absent target profile
is reported as `vanish`. These are distinct from comparing a declared profile
with an empty grain. If both profiles are absent, no comparison applies.

| Relationship | Source compared with target |
| --- | --- |
| `same` | Both select the same dimensions and resolutions. |
| `expand` | The target refines the source by adding dimensions or selecting finer resolutions. |
| `collapse` | The target is coarser by removing dimensions or selecting coarser resolutions. |
| `emerge` | No source profile exists; the operator introduces data at the target grain. |
| `vanish` | No target profile exists; the operator consumes the source grain without producing a profile. |
| `unrelated` | Neither grain refines the other through the declared hierarchy. |
| `not_applicable` | A declared source cannot be resolved, or a profile grain is invalid. |

The comparison uses resolution hierarchy, not dimension counts. Sources include
logical feature owners and dataframe profiles. These labels do not perform
calculations or select a merge.

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
