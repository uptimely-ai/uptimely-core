# Examples

These examples show how to define analytics projects and explore how their
parts fit together.

## Examples

| Directory | What it demonstrates |
| --- | --- |
| [`pump_analytics/`](pump_analytics/) | An end-to-end pump analytics project authored in Python and exported to JSON. |
| [`simple_analytics/`](simple_analytics/) | A small analytics definition assembled in Python and exported to JSON. |
| [`escape_operation/`](escape_operation/) | An uncontrolled workflow that reads, calculates, and writes internally. |

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
Rebuild after changing the example's source files.

```sh
uptimely build --project-root examples/pump_analytics --verbose
```

### Run the calculations

```sh
uptimely run --project-root examples/pump_analytics
```

### Open the project explorer

```sh
uptimely explore --project-root examples/pump_analytics
```

Open <http://127.0.0.1:8001/> to view the Explorer.
