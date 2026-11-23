# Build orchestrator tasks from invocations

You can skip the Uptimely Engine and create one orchestrator task for each
execution-plan invocation.

This works when task inputs and outputs can be serialized, or when you persist
results between tasks. You must handle the dataframe state that the Engine
usually keeps in memory.

## Choose a suitable workload

For example, a demand-forecasting workflow might prepare features, train
several model variants on different GPU resources, and select the best model.
Each training run may need its own schedule, retries, and monitoring.

The feature task can write its output, and each training task can read it.

## Define artifact references

The execution plan does not define how remote tasks exchange artifacts. Your
integration needs to do that.

For example:

```text
artifact:<invocation-id>
```

The reference can point to an orchestrator artifact or a file in object
storage.

Arrow IPC is suitable for dataframe exchange between tasks:

```text
Task A
  → dataframe as Arrow IPC
  → shared artifact storage
  → artifact URI
  → Task B
```

Prefect can coordinate the tasks, but your integration must write and load the
Arrow IPC files. Return a URI from the task instead of returning the whole
dataframe. Materialize lazy frames before writing them because a lazy execution
graph cannot move between processes.

## Convert the plan to Prefect tasks

```python
# example
from prefect import flow, task


@task
def invoke(invocation: dict, inputs: dict) -> str:
    arguments = load_arguments(invocation["arguments"], inputs)
    result = load_function(invocation["entrypoint"])(**arguments)
    return persist(invocation["id"], result)


@flow
def run_plan(plan: dict) -> dict[str, str]:
    futures = {}
    for invocation in plan["invocations"]:
        dependencies = {
            dependency_id: futures[dependency_id]
            for dependency_id in invocation["semantics"]["dependency_ids"]
        }
        futures[invocation["id"]] = invoke.submit(
            invocation,
            dependencies,
        )

    return {invocation_id: future.result() for invocation_id, future in futures.items()}
```

`load_function` imports the entrypoint. `load_arguments` reads any Arrow IPC
inputs. `persist` writes the result and returns its URI.

The plan must list invocations after their dependencies.
