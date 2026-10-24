# Spec vocabulary

These modules define the spec's shared operation, argument-type, and reference
vocabulary. Components that author, validate, compile, or execute specs use the
same definitions.

<div class="api-reference" markdown="1">

## Function operations

`uptimely.spec.operations` defines supported operations, return kinds, and
operation-level dataframe input rules.

::: uptimely.spec.operations
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - FunctionOperation
        - FunctionReturns
        - FUNCTION_OPERATIONS
        - FRAGMENT_OPERATIONS
        - DATAFRAME_INPUT_COUNTS
        - OPERATION_RETURN_KINDS

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
