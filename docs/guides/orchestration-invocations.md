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
def invoke(invocation: dict, inputs: dict) -> str | None:
    arguments = load_arguments(invocation["arguments"], inputs)
    result = load_function(invocation["entrypoint"])(**arguments)
    if invocation["returns"] is not None:
        return persist(invocation["returns"], result)
    return None


@flow
def run_plan(plan: dict) -> dict[str, str]:
    invocations = {item["id"]: item for item in plan["invocations"]}
    values = {}
    previous = None
    for stage in plan["stages"]:
        for invocation_id in stage:
            invocation = invocations[invocation_id]
            previous = invoke.submit(
                invocation, values, wait_for=[previous] if previous is not None else []
            )
            if invocation["returns"] is not None:
                values[invocation["returns"]] = previous
    if previous is not None:
        previous.result()
    return {name: future.result() for name, future in values.items()}
```

`load_function` imports the entrypoint. `load_arguments` resolves parameters,
paths, and named returns, reading any Arrow IPC inputs. `persist` writes a named
result and returns its URI. The example preserves stage order, including calls
with side effects and no return.
