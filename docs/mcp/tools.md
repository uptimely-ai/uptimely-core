# Tool reference

The signatures below use Python notation to describe MCP tool arguments.
The AI client calls these tools, not ordinary Python function imports.
All tools return JSON text. See [MCP setup and usage](index.md) for connecting
a client and example questions.

## Explore the model

`describe_spec() -> str`
: Counts features, functions, operators, dimensions, and profiles in the saved Spec.

`list_functions() -> str`
: Lists function IDs, categories, and return contracts.

`describe_function(function_id: str) -> str`
: Describes arguments, the Python signature, and operator usages.

`list_operators() -> str`
: Lists bound calculations, inputs, outputs, and availability in the saved plan.

`list_calculated_features() -> str`
: Lists calculated feature IDs.

`describe_feature(feature_id: str) -> str`
: Explains the producing function and direct and transitive dependencies.

## Run analytics

`execute_function(function_id: str, profile_id: str | None = None, operator_id: str | None = None, max_rows: int = 50) -> str`
: Runs one function through its operator and dependencies. Use profile or operator
  IDs to disambiguate reused functions.

`execute_operator(profile_id: str, operator_id: str, max_rows: int = 50) -> str`
: Runs one operator and its dependencies, excluding later work and output writers.

`execute_build(max_rows: int = 50) -> str`
: Runs the entire saved plan, including configured output writers.

`max_rows` limits returned samples, not calculation inputs. Explicitly selecting
an output writer still runs it. Custom functions can also have side effects.

## Inspect the latest run

`describe_last_run() -> str`
: Returns saved status, timing, failures, and profile summaries.

`read_last_run_logs(level: str | None = None, offset: int = 0, limit: int = 100, run_id: str | None = None) -> str`
: Reads logs, optionally filtered by `DEBUG`, `INFO`, `WARNING`, `ERROR`, or
  `CRITICAL`. `limit` accepts 1 to 1,000 events. Use the returned `next_offset` for
  another page and `run_id` to check that the run has not changed.

## Inspect or refresh the build

`describe_build() -> str`
: Reports the saved version and feature scope.

`reload_build() -> str`
: Reloads the saved Spec and plan after a successful project build.
