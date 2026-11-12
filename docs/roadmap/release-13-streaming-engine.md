# Release 13: Stateful micro-batch streaming with checkpoints and restart recovery

This is a planned release grouping, not a published software version.

The first streaming engine runs one bounded micro-batch per invocation and then
exits. Users or external schedulers invoke it repeatedly. It does not run as a
server, manage a continuous polling loop, or require distributed workers.

Streaming means that successive runs continue the same logical processing
stream. Persist source progress and the analytical state needed by the next
batch under `.cache/uptimely/streams/<stream-id>/`, separate from runtime
installation caches and generated run outputs. Saving logs or completed results
alone does not provide streaming semantics.

Although stored under `.cache/`, checkpoints are operational state rather than
disposable performance data. The first version targets replayable sources.
Deleting state requires an explicit reset and replay policy, not silent
continuation from an assumed position. Machine-local storage is not a durable,
multi-node state service.

## Work package: Micro-batch progress and state contracts

Define continuity between otherwise independent engine invocations.

**Prerequisites:** Runtime configuration and scoped execution;
Reproducible builds and diagnostics.

| title | breaking | description |
|---|---|---|
| Define stream identity and source progress | No | Associate a stream with its build, effective execution scope, and non-sensitive source configuration. Define a source contract for bounded reads, checkpointable cursors or offsets, deterministic replay, and empty batches. Keep ingestion progress distinct from event time and result freshness. Reject sources that cannot meet the initial replay contract rather than claiming arbitrary batch readers are streaming readers. |
| Define persisted analytical state | No | Declare which operators can process each batch independently and which need explicitly serialized state across batches. Define supported state schemas, initialization, update, and retention limits. Initially support stateless transformations and bounded stateful operations with explicit contracts. Reject ordinary batch aggregations or windows that cannot preserve their meaning incrementally. |
| Define restart and compatibility rules | No | Specify checkpoint format versions, build and configuration compatibility, and explicit reset or replay behavior after incompatible changes. Define initial input-order assumptions and handling of repeated or out-of-order records. Defer general event-time watermarks, late-data corrections, and unbounded windows rather than treating a source cursor as an event-time completeness guarantee. |

## Work package: Local checkpoint persistence and recovery

Make committed progress and analytical state recoverable across process exits.

**Prerequisites:** Micro-batch progress and state contracts.

| title | breaking | description |
|---|---|---|
| Persist checkpoint generations | No | Store source progress and analytical state together under `.cache/uptimely/streams/<stream-id>/` using versioned metadata and supported adapter serialization. Materialize required frames explicitly and preserve schema, grain keys, and types. Commit complete checkpoint generations atomically, retain the previous committed generation until success, and report corrupt or incompatible state instead of silently starting over. Keep secrets out of persisted metadata. |
| Enforce single-writer ownership | No | Prevent overlapping invocations from updating the same stream state. Define lock ownership, interrupted-run recovery, and explicit state inspection and reset operations. Keep runtime installation cache cleanup separate from stream reset, and document backup, replay, retention, and disk-capacity requirements. |
| Verify persistence failures | No | Test interrupted writes, process termination, corrupt state, disk failures, concurrent invocation attempts, incompatible builds, and explicit resets. Recovery must use the last complete checkpoint and must not advance input progress when corresponding analytical state was not committed. |

## Work package: Resumable micro-batch execution

Reuse the batch engine while loading and committing stream state around each
bounded run.

**Prerequisites:** Local checkpoint persistence and recovery;
Frame adapter contracts.

| title | breaking | description |
|---|---|---|
| Execute one resumable batch | No | Add explicit streaming options to the CLI and Python engine API using shared execution logic. Load the last committed state, read a bounded input batch, execute supported transformations and state updates, then commit progress only after successful processing and required output publication. Preserve existing batch execution when streaming is not selected. Handle empty input without a busy loop or unintended state changes. |
| Define output and failure guarantees | No | Document at-least-once processing on replay. Require idempotent output publication or an explicit deduplication contract for supported sinks, using stable stream and batch identities. A crash after external output publication but before checkpoint commit can repeat that output. Do not claim exactly-once behavior across arbitrary external writes or allow retries to silently duplicate unsupported side effects. Preserve validation failures, execution errors, and actionable recovery diagnostics. |
| Demonstrate and verify continuity | No | Add a replayable local-source example showing separate process invocations, restored progress, and a bounded stateful calculation. Compare incremental results with batch results for the supported semantics. Test multiple batches, restarts, empty input, repeated input, failed processing and publication, retention limits, and crash recovery. Document external scheduling, local-state limitations, reset and replay procedures, and deferred server and event-time capabilities. |
