# Examples

The examples demonstrate how Uptimely Core describes industrial analytics as a declarative specification, resolves feature dependencies, and produces executable plans and an interactive analytics explorer.

## Explore the example project

From the project root, export the specification, then build and serve the pump
analytics explorer with:

```sh
uptimely spec export \
  --module examples.pump_analytics.config.spec.spec \
  --output examples/pump_analytics/_generated/spec/spec.json
uptimely explorer serve --project-root examples/pump_analytics
```

Open <http://localhost:8001/> to view it. Stop the server with **Ctrl+C**.

## Examples

| Directory | What it demonstrates |
| --- | --- |
| [`pump_analytics/`](pump_analytics/) | An end-to-end pump analytics project authored in Python and exported to JSON. |
| [`simple_analytics/`](simple_analytics/) | A small specification assembled in Python, converted through the canonical model, and exported to JSON. |

## Folder structure

```text
examples/
├── README.md
├── pump_analytics/
│   ├── config/
│   │   ├── engine.json       Engine settings and runtime bindings
│   │   └── spec/             Flat Python specification declarations
│   │       ├── spec.py
│   │       ├── dataset_pump.py
│   │       ├── dataset_telemetry.py
│   │       ├── entity.py
│   │       ├── dimension.py
│   │       └── functions.py
│   ├── data/                 Input and calculated example datasets
│   ├── functions/            Read, vectorize, and write function implementations
│   └── _generated/
│       ├── compile/          Compiled plans
│       ├── explorer/         Generated analytics explorer
│       └── spec/             Exported declarative analytics specification
└── simple_analytics/
    ├── config/
    │   └── spec/             Python specification declarations
    ├── data/                 Data used by the Python example
    ├── functions/            Example function implementations
    └── _generated/
        └── spec/             Exported specification output
```

## Quick start

With Python 3.13 or newer, install the package, download the examples and explore the analytics project:

```sh
pip install uptimely-core
uptimely examples download
uptimely explorer serve --project-root examples/pump_analytics
```

Additional commands to try:

```sh
uptimely spec export --module examples.pump_analytics.config.spec.spec --output examples/pump_analytics/_generated/spec/spec.json
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

## Export Python specifications

The workflow commands consume JSON, so export the Python declarations before
building plans or the explorer. Re-export after changing the declarations.
From the repository root (or the parent of downloaded examples), run:

```sh
uptimely spec export \
  --module examples.pump_analytics.config.spec.spec \
  --output examples/pump_analytics/_generated/spec/spec.json
uptimely spec export \
  --module examples.simple_analytics.config.spec.spec \
  --output examples/simple_analytics/_generated/spec/spec.json
```

Prefix commands with `poetry run` in a Poetry environment.
Each declaration module exposes a `python_specification` instance of
`uptimely.analytics.python.PythonAnalytics`. The module is imported using
the current working directory unless `--project-root` supplies an import root.
Without `--output`, JSON is written to `_generated/spec/spec.json` beneath
that root. An explicit output path is relative to the current working directory.

See each example's README for details.
