# Orchestrate production runs

An orchestrator decides when to run deployments and submits their physical
execution units. The Engine executes the analytical plan, while the runtime
supplies the worker environment.

## Compile before orchestration

The Compiler converts a Spec into a logical plan describing dependencies,
arguments, outputs, and dataframe contracts. It does not select a host or
scheduler.

The current Engine executes a saved build in one Python process. This is
suitable for local development, debugging, and testing.
An orchestrator can run the same build in production.

```text
Spec
  ↓
Compiler
  ↓
Execution plan
  ↓
Orchestrator or deployment backend
  ↓
Worker
  ↓
Engine
```

See [Orchestration](../concepts/orchestration.md) for the scheduler,
orchestrator, worker, Engine, and runtime responsibilities.

## Start with one build as one job

The simplest model submits the complete build as one job:

```text
One build
  ↓
One orchestrator job
  ↓
One worker
  ↓
One Engine
  ↓
Complete execution plan
```

The orchestrator does not need to understand invocations, stages, bindings, or
dataframe state. It launches the worker and tracks job state.

The worker retains invocation-level state in Uptimely's run artifacts.

```json
{
  "bundle_uri": "s3://uptimely/builds/build-123.zip",
  "configuration": "production",
  "result_uri": "s3://uptimely/runs/run-456/"
}
```

An orchestrator-specific job can use any equivalent request format:

!!! tip "Use your own orchestrator today"

    Uptimely does not provide a deployment adapter, but it does not need one
    for a custom integration. Configure your orchestrator to start
    `uptimely run` in an environment that contains the project, saved build,
    implementation code, and required packages. The orchestrator can track the
    outer job while Uptimely records invocation-level results.

## Run from your orchestrator

If you build your own deployment integration, configure it to provide project
or build artifact availability, scheduler or orchestration API calls,
submission identity, status mapping, cancellation, and target-specific
deployment policy.

The integration need not copy the Compiler's graph when it runs the complete
build.

The local Python API is currently available:

```python
# example
from uptimely import Uptimely

application = Uptimely()
application.build()
result = application.run()
```

This runs the Engine in the current Python process.

If Prefect is installed in the same environment as the Uptimely project and
its Python dependencies, a flow can run the existing API directly:

```python
# example
from prefect import flow
from uptimely import Uptimely


@flow
def run_uptimely_build(project_root: str) -> object:
    application = Uptimely(project_root, config="production")
    return application.run()


if __name__ == "__main__":
    run_uptimely_build(".")
```

The flow runtime needs the project, saved build, and analytical packages. The
same pattern works with Dagster, Kubernetes Jobs, CI runners, and similar
systems:

```python
import subprocess

subprocess.run(["uptimely", "build"], check=True)
subprocess.run(["uptimely", "run"], check=True)
```

The integration owns runtime preparation, project transfer, configuration,
secrets, and result storage. It can use Docker, Kubernetes, virtual
environments, or a managed platform.

## Track one build and its invocations

The orchestrator and Uptimely report different results:

| Level | Responsible component | Example state |
| --- | --- | --- |
| Overall job | Orchestrator | Queued, running, succeeded, failed, cancelled |
| Analytical steps | Uptimely | Invocation succeeded, failed, or skipped |

Uptimely writes invocation details to its latest run artifacts. A custom
integration can upload those artifacts or read `run.json`.

When possible, store both IDs together:

```text
Orchestrator run ID
  → Uptimely run and invocation IDs
```

Do not create an orchestrator task for every invocation. One task for the whole
build avoids duplicated dependencies and unnecessary process boundaries.

For an advanced invocation-per-task integration, see
[Build orchestrator tasks from invocations](orchestration-invocations.md).

## Choose an execution backend

Choose orchestration and infrastructure independently.

| Pattern | Orchestration and scheduling | Execution backend |
| --- | --- | --- |
| Local development | Uptimely CLI | Local process or Docker |
| Single production job | Cron, cloud scheduler, or managed orchestrator | Docker, Kubernetes Job, or virtual machine |
| Workflow orchestration | Prefect or Dagster | Containers or platform-native jobs |
| Distributed Python and dataframes | Workflow orchestrator | Kubernetes, distributed runtime, or managed compute |
| Snowflake-oriented analytics | External scheduler or Snowflake Task | Snowflake or Snowpark |

Users can assemble these combinations today. Uptimely runs inside the selected
environment, while the platform supplies scheduling and runtime preparation.

Kubernetes is an infrastructure backend. Its scheduler places pods on nodes,
but does not model Uptimely invocation dependencies.

Managed data platforms can act as compute backends. Their job mechanisms do
not necessarily replace a workflow scheduler.

## Choose based on workload

Use the least complex user-owned setup that satisfies the workload:

1. Use a local process for fast development and debugging.
2. Package the project in a user-managed Docker image for isolated execution.
3. Submit one whole-build job for the first production deployment.
4. Let the orchestrator track the outer job and collect Uptimely's run
   artifacts.
5. Keep the whole build in one process until multiple workers are needed.

This keeps the Compiler and Engine independent of an orchestrator. Users can
add Prefect, Dagster, Kubernetes, or managed platforms without changing the
plan.

!!! tip "Available today"

    Run `uptimely build` followed by `uptimely run` in any user-managed
    environment. Prefect, Dagster, Docker, Kubernetes, and managed schedulers
    can provide the surrounding setup.
