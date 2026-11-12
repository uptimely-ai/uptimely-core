# Release 3: Dataframe interoperability, distributed adapters, and tensor features

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Work package: Additional dataframe adapters

Extend supported libraries without conflating interchange with native assembly.

**Prerequisites:** Frame adapter contracts and their conformance suites.
Parallel scheduling is not required for an adapter to ship.

| title | breaking | description |
|---|---|---|
| Add conversion adapters and native implementations as needed | No | Start with pandas interchange and add DuckDB and PyArrow support for concrete workflows. Document capabilities and run the applicable conformance suites; conversion does not imply native assembly. Polars remains the default. NumPy and PyTorch can be used inside function bodies without requiring tensor feature support. |
| Add a mixed-library dataframe example | No | Demonstrate user-written conversion decorators, explicit module loading and Polars assembly of foreign fragments. Show native pass-through, conversions, unsupported types and actionable missing-capability errors. |
| Show conversion and assembly points in Explorer | No | Display known representation changes, selected assembly implementations and materialization requirements. Mark unresolved boundaries explicitly rather than claiming the portable compiler can infer every conversion. |
## Work package: Distributed dataframe adapters

Add remote-native execution only for workflows that need it, after local
contracts, configuration, tests and diagnostics are established.

**Prerequisites:** Frame adapter contracts and conformance suites;
Runtime configuration and scoped execution; Analytics CI/CD workflow;
Execution reports and inspection for report export, not its Explorer view.

| title | breaking | description |
|---|---|---|
| Add PySpark and Snowpark native execution support | No | Support cluster-native inspection, validation and assembly; Arrow conversion alone is not distributed execution. Keep frames and joins remote on native paths. Show remote-to-local transfer in the plan and require explicit permission, such as `uptimely run --allow-remote-transfer`, with transfer limits. Missing native capabilities must not implicitly collect into Polars. Test remote failure and transfer diagnostics and expose them in execution reports. |

## Independently scheduled dataframe upgrades

Ship these packages when their specific prerequisites and user needs justify
them, without waiting for every adapter.

### Polars 2.0 upgrade

**Prerequisites:** An available upstream software release and successful compatibility
testing. Neither the upgrade nor the adapter redesign inherently blocks the other.

| title | breaking | description |
|---|---|---|
| Upgrade built-in Polars support to 2.0 | Maybe | Update the dependency range and adapt the built-in backend, tests and documentation to Polars 2.0. Assess breaking APIs and document migration for projects using Polars directly. |

### Tensor features

**Prerequisites:** Frame adapter contracts, including portable type and
missing-value rules.

| title | breaking | description |
|---|---|---|
| Add a tensor feature type | No | Support fixed-shape tensor features using Arrow's `FixedShapeTensor` type, with explicit shape, dtype and conversion contracts tested through the applicable adapter conformance suites. |
