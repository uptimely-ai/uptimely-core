# Release 3: Dataframe interoperability, distributed adapters, and tensor features

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Work package: Additional dataframe adapters

Extend supported libraries without conflating interchange with native assembly.

**Prerequisites:** Dataframe adapter API and registry, Function representation
and type contracts, Arrow conversion and assembly, and Adapter conformance suites.
Parallel scheduling is not required for an adapter to ship.

| title | breaking | description |
|---|---|---|
| Add pandas conversion support | No | Add a pandas adapter for supported interchange workflows and run the applicable conformance suite. Conversion does not imply native assembly. |
| Add DuckDB and PyArrow adapters | No | Add adapters for concrete DuckDB and PyArrow workflows, declaring conversion and native assembly capabilities separately. |
| Document adapter capabilities | No | Document supported capabilities and keep Polars as the default. NumPy and PyTorch remain usable inside functions without tensor feature support. |
| Add a mixed-library dataframe example | No | Demonstrate user-written conversion decorators, explicit module loading and Polars assembly of foreign fragments. Show native pass-through, conversions, unsupported types and actionable missing-capability errors. |
| Show conversion and assembly points in Explorer | No | Display known representation changes, selected assembly implementations and materialization requirements. Mark unresolved boundaries explicitly rather than claiming the portable compiler can infer every conversion. |

## Work package: Distributed dataframe adapters

Add remote-native execution only for workflows that need it, after local
contracts, configuration, tests and diagnostics are established.

**Prerequisites:** Dataframe adapter API and registry, Arrow conversion and
assembly, Adapter conformance suites, Runtime environments and preflight, and
Analytics CI/CD workflow.
Execution reports and inspection for report export, not its Explorer view.

| title | breaking | description |
|---|---|---|
| Add PySpark native execution | No | Support cluster-native inspection, validation, and assembly. Keep frames and joins remote on native paths. |
| Add Snowpark native execution | No | Support cluster-native inspection, validation, and assembly. Keep frames and joins remote on native paths. |
| Require explicit remote-to-local transfer | No | Show transfers in the plan and require explicit permission, such as `uptimely run --allow-remote-transfer`, with limits. Never implicitly collect to Polars when a native capability is missing. |
| Verify distributed adapter failures | No | Test remote failures and transfer diagnostics, and expose them in execution reports. Arrow conversion alone does not provide distributed execution. |

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

**Prerequisites:** Function representation and type contracts, Null and
missing-value semantics.

| title | breaking | description |
|---|---|---|
| Add a tensor feature type | No | Support fixed-shape tensor features using Arrow's `FixedShapeTensor` type, with explicit shape, dtype and conversion contracts tested through the applicable adapter conformance suites. |
