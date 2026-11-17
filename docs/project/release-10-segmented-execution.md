# Release 10: Arrow IPC segments and parallel, multi-node execution

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Work package: Worker control and exchange contracts

Define a language-neutral worker interface separating tabular exchange from
execution control.

**Prerequisites:** Arrow conversion and assembly, Destination bundle preparation.

| title | breaking | description |
|---|---|---|
| Define the versioned worker control envelope | No | Carry execution, segment, and invocation IDs, scalar arguments, artifact references, schemas, grain keys, preservation requirements, statuses, and diagnostics. |
| Define Arrow IPC dataframe exchange | No | Use Arrow IPC for dataframe inputs and outputs across runtime and incompatible-representation boundaries. |
| Separate transport from encoding | No | Allow local files/pipes and later remote artifact stores to carry the same worker contract. |
| Reference non-tabular artifacts explicitly | No | Keep models and other artifacts behind explicit references rather than treating arbitrary tensors as tabular IPC payloads. |

## Work package: Python worker IPC implementation

Implement dataframe exchange using existing adapter contracts and validate
the worker protocol.

**Prerequisites:** Worker control and exchange contracts, Adapter conformance
suites.

| title | breaking | description |
|---|---|---|
| Reuse adapter conversion contracts | No | Keep native frames within compatible work and materialize explicitly at IPC boundaries. |
| Preserve data semantics at worker boundaries | No | Preserve declared key, order, and type semantics. Reject unsupported objects and conversions. |
| Test and document worker protocols | No | Test round trips, empty inputs, malformed messages, schema fidelity, and protocol mismatches. Document the non-Python worker contract. |

## Work package: Compiler execution segmentation

Identify compatible subgraphs and independent work without conflating
dependency levels with distributed data partitions.

**Prerequisites:** Worker control and exchange contracts, Python worker IPC
implementation.

| title | breaking | description |
|---|---|---|
| Add execution segments to compiled plans | Yes | Preserve invocation dependencies and scheduling stages while assigning separate identities to execution segments. |
| Cut segments at runtime and representation boundaries | Yes | Record Arrow IPC contracts and materialization points at runtime changes and incompatible representations. |
| Group compatible work safely | Yes | Group work only when dependencies and preservation semantics allow it. Preserve native lazy optimization and leave unknown representations unresolved until target-aware planning. Fail execution if planning cannot resolve them. |
| Preserve publication and side-effect ordering | No | Record isolated computation outputs and explicit merge/publication dependencies. Preserve side-effect order and report work with unknown concurrency safety. |
| Keep invocation concurrency distinct from partitioning | No | Do not treat shared profile mutations as parallel-safe. Record partitionability separately because it needs aggregation, window, and state contracts. |

## Work package: Segmented plan reporting and verification

Expose compiler-produced segments clearly and verify their dependency coverage.

**Prerequisites:** Compiler execution segmentation.

| title | breaking | description |
|---|---|---|
| Verify compiled segment dependencies | No | Test branched graphs, joins, shared consumers, and representation/runtime changes. Verify stable IDs and complete dependency coverage. |
| Serialize and expose segmented plans | No | Update serialization, validation, diagnostics, and Explorer to distinguish stages, segments, and interchange boundaries. |
| Verify segmented plan equivalence | No | Compare supported fixtures with unsegmented execution. Document that identified concurrency alone does not provide multi-node execution. |

## Work package: Sequential cross-runtime graph execution

Run segmented graphs correctly before adding concurrent or remote scheduling.

**Prerequisites:** Segmented plan reporting and verification,
Launcher equivalence and documentation.

| title | breaking | description |
|---|---|---|
| Submit ready segments sequentially | Yes | Drive ready segments through venv or Docker workers and pass Arrow IPC artifacts. |
| Publish successful segment results | Yes | Publish outputs only after success and load implementations only in their assigned runtime. |
| Preserve engine run and failure semantics | Yes | Preserve merge contracts, validation, whole-graph outputs, per-invocation status, and explicit downstream skipping after failures. |
| Verify mixed-runtime execution | No | Test incompatible dependency versions, mixed representations, IPC and startup failures, artifact cleanup, and result equivalence. |
| Document hardware and driver execution | No | Add CPU/GPU configuration examples with hardware-independent routine fixtures and explicit hardware integration checks. Keep the single-runtime launcher available and document driver execution. |

## Work package: Parallel and multi-node segment driving

Schedule compiler-identified segments across workers without duplicating
planning in deployment adapters.

**Prerequisites:** Sequential cross-runtime graph execution;
Plan optimization and bounded concurrency.

| title | breaking | description |
|---|---|---|
| Schedule ready segments concurrently | No | Extend the bounded scheduler with dependency-aware readiness and isolated segment outputs. |
| Bound worker resources and reuse | No | Apply global and per-runtime limits. Account for library threading, memory, transfer costs, and worker reuse rather than starting one process per callable. |
| Publish concurrent results deterministically | No | Publish outputs deterministically and test sequential/concurrent equivalence and failure propagation, including side effects and shared profile consumers. |
| Submit segments to remote workers | No | Add multi-node submission and Arrow IPC artifact references with explicit transfer limits. Keep placement in deployment configuration. |
| Manage remote worker lifecycle | No | Add status reporting, cancellation, cleanup, and retry policy with idempotency requirements for side effects. |
| Verify remote execution boundaries | No | Test remote failures and distinguish segment distribution from record partitioning and distributed-native dataframe adapters. Allow orchestrators to submit segment jobs without rebuilding dependencies. |
