# Function contracts

`uptimely.contracts` defines the operation types, allowed return kinds, and
reference syntax shared by spec definitions and execution plans.

<div class="api-reference" markdown="1">

## Operation types and rules

`FunctionOperation` describes the supported operations. `FunctionReturns`
distinguishes dataframe-producing functions from functions that return no data.
The lookup tables describe input counts and return kinds for each operation.

::: uptimely.contracts
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

## Reference syntax

These constants define dataset, feature, and dimension reference prefixes,
the current-dataset marker, and selectors for identifiers and dataframes.

::: uptimely.contracts
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
