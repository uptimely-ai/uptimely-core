# Validate execution

## Python runtime preflight

Before running any operator, the Engine checks the bundle's Python version
constraint and verifies that dependencies whose environment markers match are
installed at compatible versions. This check reports missing or incompatible
dependencies together with any Python version mismatch.

The Engine does not install dependencies or verify transitive dependencies,
extras, or direct URL provenance. Bundles without a runtime definition skip
this check. See [Build bundle runtime requirements](../artifacts/build.md#runtime-requirements)
for how the metadata is generated.

## Runtime validation

Analytical runtime validation is optional and disabled by default. Enable it with
`uptimely run --validate` or `Engine.run(validate=True)`. Checks depend on the
invocation's analytical semantics:

| When | Validation |
| --- | --- |
| Before every call | The invocation has analytical semantics. |
| Before every call | Each supplied argument declared as a dataframe is a Polars dataframe or lazy dataframe. An optional dataframe may be `None`. Arguments not supplied are not checked. |
| Before a call with declared dataframe arguments | Declared input features appear across the supplied dataframes. |
| Before a call with target or foreign dataframe scope | Exactly one supplied dataframe is a named plan result. Target scope requires a dataset or merge result for the target profile. Foreign scope requires a different result reference. |
| Before a call with target dataframe scope | The target satisfies the dataframe checks below. Declared output columns do not already exist in it. |
| Before a merge | The `dataset` and `fragment` arguments are present. The fragment is a dataframe, and the dataset is a dataframe or `None` when its declared type permits it. Both present frames satisfy the dataframe checks below. Non-key fragment columns do not overlap the dataset. |
| After a dataframe-producing call | The result is a dataframe satisfying the dataframe checks below and contains every declared output column. Extra columns are allowed. |
| After a call declaring row-count preservation | The result has the same number of rows as the target input. |
| After a call declaring identical keys | The result has the same target identifier keys as the input, regardless of order. |
| After a call declaring row-order preservation | The target identifier sequence matches the input when identifiers are declared. |
| After a target-result call declaring existing-data preservation | All input columns and values are retained. Values are compared in row order when order preservation is declared, otherwise by identifier keys. |
| After a merge | The result satisfies the target dataframe checks below and contains exactly the union of the input columns. |

The dataframe checks apply to target inputs, merge inputs, and dataframe results.
For fragments at a subset of the target grain, the available declared target and
fragment keys determine the identifiers when the full target identifiers are absent.

| Dataframe check | Validation |
| --- | --- |
| Identifier columns | All identifiers selected for the frame are present. |
| Identifier uniqueness | Identifier combinations are unique. A frame without identifiers has at most one row. |
| Column types | Present columns with declared types match their logical types. Output type declarations take precedence over other column type declarations. |

Preservation checks require a target input for comparison. Results declared as
`none` have no post-call result check. Merge validation checks result columns,
identifiers, and types, but does not compare the merged values with the inputs.

Validation does not modify the arguments or results of calls. On a failure, the
Engine stops before later calls and does not publish the failing result.
Validation cannot undo mutations or external side effects already performed by
a function. Checks on lazy dataframes can execute upstream queries multiple
times, so their inputs should be stable across evaluations.
See [Engine execution](../concepts/engine.md#plan-execution) for execution order
and failure handling.

## Runtime validation and configuration

See [Configure a project](configuration.md#runtime-values) for runtime values,
paths, parameters, and backend settings.
