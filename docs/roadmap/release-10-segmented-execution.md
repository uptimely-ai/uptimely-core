# Release 10: Arrow IPC segments and parallel, multi-node execution

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Work package: Arrow IPC worker boundaries

Define a language-neutral worker interface separating tabular exchange from
execution control.

**Prerequisites:** Frame adapter contracts; Portable ZIP execution bundles.

| title | breaking | description |
|---|---|---|
| Define worker requests and tabular exchange | No | Use Arrow IPC for dataframe inputs and outputs across runtime and incompatible-representation boundaries. Define a separate versioned control envelope for execution, segment, and invocation IDs, scalar arguments, artifact references, schemas, grain keys, preservation requirements, statuses, and diagnostics. Keep transport separate from encoding so local files/pipes and later remote artifact stores can carry the same contract. |
| Implement and validate the Python worker protocol | No | Reuse adapter conversion contracts, retaining native frames within compatible work. Materialize at IPC boundaries explicitly, preserve declared key/order/type semantics, and reject unsupported Python objects or conversions. Keep non-tabular models and other artifacts behind explicit references rather than assuming arbitrary tensors are tabular IPC payloads. Test round trips, empty inputs, malformed messages, schema fidelity, and protocol mismatches, and document the non-Python worker contract. |

## Work package: Compiler execution segmentation

Identify compatible subgraphs and independent work without conflating
dependency levels with distributed data partitions.

**Prerequisites:** Arrow IPC worker boundaries.

| title | breaking | description |
|---|---|---|
| Compile execution segments and boundary contracts | Yes | Retain invocation dependencies and scheduling stages, and add separately identified execution segments. Cut flows at runtime changes and incompatible dataframe representations, recording Arrow IPC input/output contracts and materialization points. Group compatible work only when dependencies and preservation semantics permit it, preserving native lazy optimization. Leave unknown representation choices unresolved until target-aware planning and fail if execution cannot resolve them. |
| Preserve publication and side-effect dependencies | No | Record isolated computation outputs and explicit merge/publication dependencies rather than treating shared profile mutations as parallel-safe. Preserve declared side-effect ordering and report work whose concurrency safety is unknown. Distinguish independent invocations from record partitionability, which requires separate aggregation, window, and state contracts. Test branched graphs, joins, shared consumers, representation changes within one runtime, and runtime changes using the same representation. |
| Expose segmented plans | No | Update plan serialization, validation, diagnostics, and Explorer to distinguish stages, segments, and interchange boundaries. Verify stable segment references, complete dependency coverage, and equivalence to unsegmented execution for supported fixtures. Document that compiler-identified concurrency does not by itself provide multi-node execution. |

## Work package: Sequential cross-runtime graph execution

Run segmented graphs correctly before adding concurrent or remote scheduling.

**Prerequisites:** Compiler execution segmentation;
Whole-graph isolated runtime launchers.

| title | breaking | description |
|---|---|---|
| Execute segments through isolated workers | Yes | Extend the engine into a driver that sequentially submits ready segments through venv or Docker launchers, passes Arrow IPC artifacts, and publishes results only after successful completion. Load implementations only in their assigned runtime. Preserve merge contracts, validation, whole-graph outputs, per-invocation status, and explicit downstream skipping after failures. |
| Verify mixed-runtime execution and diagnostics | No | Add CPU and GPU-runtime configuration examples, with hardware-independent worker fixtures for routine tests and explicit hardware integration checks. Cover incompatible dependency versions, mixed dataframe representations, IPC failures, artifact lifetime/cleanup, worker startup failures, and result equivalence. Keep the single-runtime whole-graph path available and document the transition to driver execution. |

## Work package: Parallel and multi-node segment driving

Schedule compiler-identified segments across workers without duplicating
planning in deployment adapters.

**Prerequisites:** Sequential cross-runtime graph execution;
Plan optimization and bounded concurrency.

| title | breaking | description |
|---|---|---|
| Schedule independent segments concurrently | No | Extend the bounded scheduler to segment jobs with global and per-runtime resource limits, dependency-aware readiness, isolated outputs, and deterministic publication. Account for library threading, memory, transfer costs, and worker reuse rather than launching one process per callable. Verify sequential/concurrent equivalence and failure propagation, including side effects and shared profile consumers. |
| Add remote placement and lifecycle controls | No | Extend the driver/launcher contract to multi-node submission and Arrow IPC artifact references with explicit remote transfer limits. Keep placement in deployment configuration, and implement status reporting, cancellation, resource cleanup, and retry policy with idempotency requirements for side effects. Test remote failures and distinguish independent-segment distribution from future record partitioning or distributed-native dataframe adapters. Orchestrator adapters may submit segment jobs through this contract without rebuilding graph dependencies. |
