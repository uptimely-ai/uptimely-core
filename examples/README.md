# Examples

The examples demonstrate how Uptimely Core describes industrial analytics,
resolves feature dependencies, and produces executable plans and an interactive
analytics explorer.

## Explore the example project

From the repository root, build the complete active bundle:

```sh
uptimely project build --project-root examples/pump_analytics
```

The spec, plan, and Explorer artifacts are generated together by this one
build command. `explorer serve` validates the active build and serves the saved
website; it does not regenerate it:

```sh
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
│   │   └── spec/             Python spec declarations
│   │       ├── spec.py
│   │       ├── dataset_pump.py
│   │       ├── dataset_telemetry.py
│   │       ├── entity.py
│   │       ├── dimension.py
│   │       └── functions.py
│   ├── data/                 Input and calculated example datasets
│   ├── functions/            Read, vectorize, and write function implementations
│   └── _generated/
│       └── build/            Active bundle: manifest, spec, plan, Explorer
└── simple_analytics/
    ├── config/
    │   └── spec/             Python spec declarations
    ├── data/                 Data used by the Python example
    ├── functions/            Example function implementations
    └── _generated/
        └── build/            Active bundle: manifest, spec, plan, Explorer
```

## Quick start

With Python 3.13 or newer, install the package, download the examples and explore the analytics project:

```sh
pip install uptimely-core
uptimely examples download
uptimely project build --project-root examples/pump_analytics
uptimely explorer serve --project-root examples/pump_analytics
```

Additional commands to try:

```sh
uptimely spec feature-graph --project-root examples/pump_analytics --verbose
uptimely engine run --project-root examples/pump_analytics

```

Run these commands from the parent of the downloaded `examples/` directory.
By default, the download uses the release tag matching the installed package
version (`v<version>`) and fails if that tag is unavailable. Use `--ref` to
select another branch, tag, or commit (`HEAD` selects the repository's default
branch), or `--output` to change the destination. The destination must not
already exist.

Generated artifacts are written beneath each example's `_generated/build/`
directory. A build validates the complete source and publishes a manifest,
full spec, execution plan, and complete Explorer website. Use
`--features <name> [<name> ...]` to select a scoped plan and its dependencies;
omit the option to build all features. The spec stays complete in either case,
while Explorer identifies the selected plan scope. Every successful build
replaces the active bundle; a failed build leaves the last successful one
available. Source edits do not regenerate artifacts, so run `project build`
explicitly before asking Engine or Explorer to use updated declarations.

Building does not execute workflow functions or sinks. Engine executes the
saved plan, including configured write sinks, and may cause external side
effects. Missing or invalid builds fail explicitly with a recovery command.
See the
[project command reference](../docs/reference/cli/project.md).

## Building from Python declarations

The project builder discovers `config/spec/spec.py` or
`config/spec/spec.json` under each project root. Build either or both examples
from the repository root (or the parent of downloaded examples):

```sh
uptimely project build --project-root examples/pump_analytics
uptimely project build --project-root examples/simple_analytics
```

Prefix commands with `poetry run` in a Poetry environment.
Each declaration module exposes a `python_spec` instance of
`uptimely.spec.python.PythonSpec`. Python sources are loaded with their package
context, preserving package-relative imports. Use `--entrypoint
module:attribute` to select a different module or declaration attribute, or
`--spec <path>` to select a JSON source. If both standard sources exist, one
must be selected explicitly.

See each example's README for details.
