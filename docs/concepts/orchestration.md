# Orchestration

Orchestration controls when analytical work runs and submits it to physical
execution environments.

Uptimely currently runs a complete saved build in one Python process. External
orchestrators can invoke that execution without understanding invocation
semantics.

## Responsibility boundaries

### Scheduler

The scheduler decides when execution starts. It can respond to schedules,
events, queues, or job dependencies.

Prefect, Dagster, cron, and cloud schedulers can provide this responsibility.

### Orchestrator

The orchestrator coordinates submitted execution units. It can manage job
submission, dependencies, retries, cancellation, placement, logs, monitoring,
and run history.

### Worker

A worker is the running process that hosts an execution request. It loads the
project or bundle, starts the Engine, and reports process-level status and
results.

The worker does not define the analytical graph. The Engine receives the plan
and executes it.

```text
Docker container or Kubernetes pod
└── Worker process
    └── Uptimely Engine
        └── Execution plan
```

Today, the Python process started by the CLI or Python API acts as the worker.
There is no separate worker component yet.

### Engine

The Engine applies Uptimely's analytical semantics. It executes invocations,
resolves dataframe inputs, maintains profile state, validates contracts, and
records invocation results.

The Engine does not select a scheduler or provision its environment.

### Runtime

A runtime supplies the worker environment and dependencies. Examples include a
Python virtual environment, Docker container, Kubernetes pod, or managed
platform.

Different workers may require different packages. Image processing, GPU model
training, and traditional dataframe calculations can use separate runtimes
when segmented execution is available.

## Execution flow

```text
Scheduler or orchestrator
  ↓
Worker process
  ↓
Uptimely Engine
  ↓
Dataframe backend
```

The Engine runs the complete plan in the current process. The current
relationship is:

```text
1 project build
  → 1 runtime
  → 1 worker process
  → 1 Engine
  → complete execution plan
```

## Worker and Engine relationship

The worker and Engine operate at different levels:

- The worker owns process startup, termination, runtime communication, and
  result transport.
- The Engine owns analytical plan execution.

A container, job, or Prefect task is not automatically an Uptimely worker. It
becomes a worker environment when it starts a process that loads and runs the
Engine.

A future long-lived worker may run several isolated Engines:

```text
Worker process
├── Engine: segment 1
├── Engine: segment 2
└── Engine: segment 3
```

This optimization is not available today.

## Execution units

Uptimely distinguishes:

- **Invocation:** one callable and its resolved arguments
- **Stage:** invocations grouped by dependency level
- **Segment:** an independently schedulable group of compatible invocations
- **Partition:** a record-level division of work

The current Engine executes stages and invocations sequentially in one process.
Segments and partitions are future execution concepts.

## Driver

A driver coordinates multiple workers and their segments. It can submit ready
segments, transfer artifacts, collect results, and handle cancellation.

Uptimely does not currently implement a separate driver. A user-managed
orchestrator can provide this responsibility around whole-build execution.
