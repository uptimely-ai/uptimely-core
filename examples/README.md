# Examples

The examples demonstrate how Uptimely Core describes industrial analytics,
resolves feature dependencies, and produces executable plans and an interactive
analytics explorer.

## Explore the example project

From the project root, export the analytics, then build and serve the pump
analytics explorer with:

```sh
uptimely analytics build --project-root examples/pump_analytics
uptimely explorer serve --project-root examples/pump_analytics
```

Open <http://localhost:8001/> to view it. Stop the server with **Ctrl+C**.

## Examples

| Directory | What it demonstrates |
| --- | --- |
| [`pump_analytics/`](pump_analytics/) | An end-to-end pump analytics project authored in Python and exported to JSON. |
| [`simple_analytics/`](simple_analytics/) | A small analytics definition assembled in Python and exported to JSON. |

## Folder structure

```text
examples/
├── README.md
├── pump_analytics/
│   ├── config/
│   │   ├── engine.json       Engine settings and runtime bindings
│   │   └── analytics/       Flat Python analytics declarations
│   │       ├── analytics.py
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
│       └── analytics/             Exported analytics JSON
└── simple_analytics/
    ├── config/
    │       └── analytics/       Python analytics declarations
    ├── data/                 Data used by the Python example
    ├── functions/            Example function implementations
    └── _generated/
        └── analytics/             Exported analytics JSON
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
uptimely analytics build --project-root examples/pump_analytics
uptimely analytics feature-graph --project-root examples/pump_analytics --verbose
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

## Export Python analytics

The workflow commands consume JSON, so export the Python declarations before
building plans or the explorer. Re-export after changing the declarations.
From the repository root (or the parent of downloaded examples), run:

```sh
uptimely analytics build --project-root examples/pump_analytics
uptimely analytics build --project-root examples/simple_analytics
```

Prefix commands with `poetry run` in a Poetry environment.
Each declaration module exposes a `python_analytics` instance of
`uptimely.analytics.python.PythonAnalytics`. By default, the command discovers
`config/analytics/analytics.py` under the project root, preserving package-relative
imports. You can also run `uptimely analytics build` from inside either example.
Use `--module` to select a different importable declaration module.
Without `--output`, JSON is written to `_generated/analytics/analytics.json` beneath
that root. An explicit output path is relative to the current working directory.

See each example's README for details.
