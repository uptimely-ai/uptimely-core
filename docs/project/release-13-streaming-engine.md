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

## Work package: Stream identity and source progress

Identify a logical stream and define how a bounded source advances.

**Prerequisites:** Scoped run options, Runtime environments and preflight,
Immutable build snapshots.

| title | breaking | description |
|---|---|---|
| Identify a logical stream | No | Associate a stream with its build, effective execution scope, and non-sensitive source configuration. |
| Define bounded source progress | No | Support bounded reads, checkpointable cursors or offsets, deterministic replay, and empty batches. Reject sources that cannot meet this contract. |
| Separate ingestion progress from event time | No | Keep source progress distinct from event time and result freshness. Do not treat a source cursor as an event-time completeness guarantee. |

## Work package: Incremental operator state contracts

Define which analytical operations can preserve their meaning across batches.

**Prerequisites:** Stream identity and source progress.

| title | breaking | description |
|---|---|---|
| Define stateless and stateful operator contracts | No | Identify operators that process batches independently and those requiring serialized state across batches. |
| Define state lifecycle and limits | No | Define supported state schemas, initialization, update, and retention limits. |
| Reject unsupported batch semantics | No | Initially support stateless transformations and bounded stateful operations. Reject ordinary aggregations or windows that cannot preserve their meaning incrementally. |

## Work package: Checkpoint and replay compatibility

Define how stream state remains valid across restarts, configuration changes,
and record ordering.

**Prerequisites:** Incremental operator state contracts.

| title | breaking | description |
|---|---|---|
| Define checkpoint compatibility | No | Version checkpoint formats and specify build/configuration compatibility plus explicit reset or replay behavior after incompatible changes. |
| Define record ordering assumptions | No | Specify initial ordering assumptions and handling of repeated or out-of-order records. |
| Defer general event-time semantics | No | Defer watermarks, late-data corrections, and unbounded windows. |

## Work package: Checkpoint generation persistence

Persist source progress and analytical state together as complete generations.

**Prerequisites:** Checkpoint and replay compatibility.

| title | breaking | description |
|---|---|---|
| Store versioned checkpoint generations | No | Store source progress and analytical state under `.cache/uptimely/streams/<stream-id>/` with versioned metadata and supported adapter serialization. |
| Preserve frame data in checkpoints | No | Materialize required frames explicitly and preserve schema, grain keys, and types. Keep secrets out of persisted metadata. |
| Commit checkpoint generations atomically | No | Retain the previous committed generation until the new generation succeeds. Report corrupt or incompatible state instead of starting over. |

## Work package: Stream state ownership and recovery

Prevent concurrent writers and expose explicit inspection, reset, and recovery
operations.

**Prerequisites:** Checkpoint generation persistence.

| title | breaking | description |
|---|---|---|
| Enforce single-writer ownership | No | Prevent overlapping invocations from updating the same stream. Define lock ownership and interrupted-run recovery. |
| Add state inspection and reset operations | No | Provide explicit state inspection and reset. Keep runtime cache cleanup separate from stream reset. |
| Document state operations | No | Explain backup, replay, retention, and disk capacity requirements. |
| Test checkpoint failure recovery | No | Cover interrupted writes, process termination, corrupt state, disk failures, concurrent invocations, incompatible builds, and explicit resets. Recover from the last complete checkpoint and never advance input progress without committing matching analytical state. |

## Work package: Resumable batch execution

Load stream state and process one bounded batch with shared engine execution.

**Prerequisites:** Stream state ownership and recovery, Arrow conversion and
assembly.

| title | breaking | description |
|---|---|---|
| Add explicit streaming API options | No | Add streaming options to the CLI and Python engine API while keeping existing batch execution unchanged when streaming is not selected. |
| Load state and execute one bounded batch | No | Load the last committed state, read one bounded batch, and execute supported transformations and state updates. |
| Commit progress after successful publication | No | Commit progress only after processing and required output publication succeed. Handle empty input without a busy loop or unintended state changes. |

## Work package: Streaming output guarantees

Make replay behavior and failures explicit for external output publication.

**Prerequisites:** Resumable batch execution.

| title | breaking | description |
|---|---|---|
| Require replay-safe output publication | No | Document at-least-once replay and require idempotent publication or explicit deduplication using stable stream and batch identities. |
| Handle output published before checkpoint commit | No | Document that a crash in this interval can repeat external output. |
| Avoid unsupported exactly-once claims | No | Do not claim exactly-once behavior across arbitrary external writes. |
| Preserve failures during replay | No | Prevent retries from silently duplicating unsupported side effects. Preserve validation and execution errors with actionable recovery diagnostics. |

## Work package: Streaming continuity example and verification

Demonstrate resumable state and verify continuity across process invocations.

**Prerequisites:** Streaming output guarantees.

| title | breaking | description |
|---|---|---|
| Demonstrate resumable execution | No | Show separate process invocations, restored progress, and a bounded stateful calculation using a replayable local source. Compare incremental and batch results for supported semantics. |
| Verify batch, restart, and crash behavior | No | Test multiple batches, restarts, empty and repeated input, failed processing/publication, retention limits, and crash recovery. |
| Document operational boundaries | No | Document external scheduling, local-state limitations, reset/replay procedures, and deferred server and event-time capabilities. |
