# Examples

These examples show how to define analytics projects and explore how their
parts fit together.

## Examples

| Directory | What it demonstrates |
| --- | --- |
| [`pump_analytics/`](pump_analytics/) | An end-to-end pump analytics project authored in Python and exported to JSON. |
| [`simple_analytics/`](simple_analytics/) | A small analytics definition assembled in Python and exported to JSON. |
| [`escape_operation/`](escape_operation/) | An uncontrolled workflow that reads, calculates, and writes internally. |

## Folder structure

```text
examples/
├── README.md
├── pump_analytics/
│   ├── config/
│   │   ├── engine.json       Engine settings
│   │   └── spec/             Analytics definitions
│   │       ├── spec.py
│   │       ├── dataset_pump.py
│   │       ├── dataset_telemetry.py
│   │       ├── entity.py
│   │       ├── dimension.py
│   │       └── functions.py
│   ├── data/                 Example input and output data
│   ├── functions/            Code that reads, calculates, and saves data
│   └── _generated/
│       └── build/            Files created by the build
├── simple_analytics/
│   ├── config/
│   │   └── spec/             Analytics definitions
│   ├── data/                 Example data
│   ├── functions/            Example function implementations
│   └── _generated/
│       └── build/            Files created by the build
└── escape_operation/
    ├── config/
    │   ├── engine.json
    │   └── spec/spec.json
    ├── data/                 Input data for the external workflow
    └── functions/            Uncontrolled workflow implementation
```

## Quick start

Python 3.13 or newer is required. Install the package, download the examples,
build the project, and open the Explorer.

With pip:

```sh
pip install uptimely-core
uptimely examples download --output examples
uptimely project build --project-root examples/pump_analytics
uptimely engine run --project-root examples/pump_analytics
uptimely explorer serve --project-root examples/pump_analytics
```

With Poetry, from your Poetry project:

```sh
poetry add uptimely-core
poetry run uptimely examples download --output examples
poetry run uptimely project build --project-root examples/pump_analytics
poetry run uptimely engine run --project-root examples/pump_analytics
poetry run uptimely explorer serve --project-root examples/pump_analytics
```

Open <http://127.0.0.1:8001/> to view the Explorer. Stop the server with
**Ctrl+C**. Run these commands from the parent directory of `examples/`.

The build creates files under `examples/pump_analytics/_generated/build/`.
Rebuild after changing the example's source files. Building does not run the
analytics; `engine run` does, and may write to configured destinations. See
the [project command reference](../docs/reference/cli/project.md) for more
options.

## Building from Python declarations

Build either or both examples from the repository root (or the parent
directory of downloaded examples):

```sh
uptimely project build --project-root examples/pump_analytics
uptimely project build --project-root examples/simple_analytics
```

In a Poetry environment, prefix each command with `poetry run`. Projects can
define their analytics in Python or JSON. Use `--python-spec module.sub_module:attribute`
to select a Python declaration, or `--json-spec <path>` to choose a JSON file.
If a project has both, select one explicitly.

See each example's README for details.
