# Examples

These examples show how to define analytics projects and explore how their
parts fit together.

Build the project to create an execution plan from its Spec. Run the project to
execute that plan.

## Examples

| Directory | What it demonstrates |
| --- | --- |
| [`pump_analytics/`](pump_analytics/) | An end-to-end pump analytics project with an uncontrolled workflow that reads, calculates, and writes internally. |

## Project folder structure

The reference folder structure used also in these examples is explained in the [project documentation](https://uptimely-ai.github.io/uptimely-core/development/project-structure/).

## Quick start

Python 3.13 or newer is required.

### Install

With pip:

```sh
pip install uptimely-core
```

With poetry:

```sh
poetry add uptimely-core
```

With poetry, add `poetry run` before the following commands.

### Download examples

Download example files `examples` directory:

```sh
uptimely examples
```

### Build the spec

The build creates files under `examples/pump_analytics/_generated/build/`.
Rebuild after changing the example's source files. Older version 1 bundles are
not supported; rebuild them from their source Specs.

```sh
uptimely build examples/pump_analytics --verbose
```

### Run the calculations

```sh
uptimely run examples/pump_analytics
```

### Open the project explorer

```sh
uptimely explore examples/pump_analytics
```

Open <http://127.0.0.1:8001/> to view the Explorer.
