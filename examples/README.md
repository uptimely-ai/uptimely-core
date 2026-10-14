# Examples

The examples demonstrate how Uptimely Core describes industrial analytics as a declarative specification, resolves feature dependencies, and produces executable plans and documentation.

## View the example documentation

From the project root, build and serve the pump analytics documentation with:

```sh
uptimely docs serve --project-root examples/pump_analytics
```

Open <http://localhost:8001/> to view it. Stop the server with **Ctrl+C**.

## Examples

| Directory | What it demonstrates |
| --- | --- |
| [`pump_analytics/`](pump_analytics/) | An end-to-end pump analytics project defined by a JSON specification. |
| [`simple_analytics/`](simple_analytics/) | A small specification assembled in Python, converted through the canonical model, and exported to JSON. |

## Folder structure

```text
examples/
├── README.md
├── pump_analytics/
│   ├── config/
│   │   ├── engine.json       Engine settings and runtime bindings
│   │   └── spec/             Python specification declarations
│   ├── data/                 Input and calculated example datasets
│   ├── functions/            Read, vectorize, and write function implementations
│   ├── _generated/
│   │   ├── compile/          Compiled plans
│   │   ├── docs/             Generated documentation
│   │   └── spec/             Exported declarative analytics specification
│   └── run_*.py              Example workflow entry points
└── simple_analytics/
    ├── config/
    │   └── spec/             Python specification declarations
    ├── data/                 Data used by the Python example
    ├── functions/            Example function implementations
    ├── _generated/
    │   └── spec/             Exported specification output
    └── run_export_spec.py    Specification export entry point
```

## Quick start

With Python 3.13 or newer, install the package and download the examples:

```sh
pip install uptimely-core
uptimely examples download
uptimely spec feature-graph --project-root examples/pump_analytics --verbose
uptimely plan build --project-root examples/pump_analytics
uptimely engine run --project-root examples/pump_analytics
```

Run these commands from the parent of the downloaded `examples/` directory.
By default, the download uses the release tag matching the installed package
version (`v<version>`) and fails if that tag is unavailable. Use `--ref` to
select another branch, tag, or commit (`HEAD` selects the repository's default
branch), or `--output` to change the destination. The destination must not
already exist.

Generated artifacts are written beneath each example's `_generated/` directory.

See each example's README for details.
