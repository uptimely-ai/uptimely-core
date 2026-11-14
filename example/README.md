# Run the cooling-pump example

This project uses synthetic telemetry for six cooling-system pumps across two
data centers and four server rooms. It demonstrates asset hierarchies,
time-based telemetry, and externally calculated measurements in an Uptimely
Core workflow.

Health scores, warning thresholds, and operating-point recommendations are
illustrative calculations. They are not validated operating limits or control
advice.

## Workflow

- `pump_telemetry` combines pump readings with asset metadata.
- `pump_series` and `pump_category` provide inherited capacity metadata. The
  `pump` profile resolves capacity from the pump, series, then category level
  and combines telemetry with external measurements.
- Time-based profiles summarize telemetry by minute, hour, and day.
- Warning profiles filter readings and summarize them by hour. The hourly
  warning profile also demonstrates an illustrative operating-point
  recommendation.
- The external workflow reads a sample CSV, calculates a measurement ratio, and
  writes its result as a separate output.

## Project files

| Path | Purpose |
| --- | --- |
| `data/input/` | Synthetic telemetry, asset metadata, constants, and external workflow inputs. |
| `data/output/` | Materialized profile results written by the workflow. |
| `src/pump_analytics.py` | Analytical calculations and profile transformations. |
| `src/pump_io.py` | Input readers, output writers, and the sample external workflow. |
| `src/pump_merge.py` | Custom merge for external measurements. |
| `src/pump_util.py` | Small helper used by the analytical functions. |
| `spec/` | Dimensions, profile declarations, and the combined Python spec. |
| `config/config.json` | Engine settings and configured input and output paths. |
| `_generated/` | The active build, Explorer snapshot, and latest run metadata. |

The Python declarations are in `spec/`. The project entry point is
`spec/spec.py`. Source modules live directly under `src/` and are imported from
the project source path. They do not need to be installed as a separate package.

## Set up the project

If you have not downloaded the example, follow the
[quick start](https://uptimely-ai.github.io/uptimely-core/#install). It shows
how to download the project. From the project root, sync its dependencies:

```console
uv sync
```

The example requires Python 3.13 or newer.

## Build and run

Build the project to compile its Python spec and publish the execution bundle:

```console
uv run uptimely build
```

Rebuild after changing profile declarations, bindings, or source functions.
Then run the workflow and preview up to ten rows from each resulting profile:

```console
uv run uptimely run --preview 10
```

The workflow writes its configured profile results under `data/output/`.
Build artifacts, the Explorer snapshot, and metadata for the latest run live
under `_generated/`. A new run replaces `_generated/run/`.

## Explore and export

To create a static copy for sharing or hosting, export the active build to a
directory or ZIP file:

```console
uv run uptimely explorer export . --output cooling-pump-analytics-explorer
uv run uptimely explorer export . --output cooling-pump-analytics-explorer.zip
```

The export uses the current build and run snapshot. Rebuild, rerun, and export
again to include later changes. See the
[CLI Explorer guide](https://uptimely-ai.github.io/uptimely-core/reference/cli/explorer/)
for export options and the
[project folder guide](https://uptimely-ai.github.io/uptimely-core/architecture/folder-structure/)
for generated and retained files.

To browse the active build locally, start the Explorer:

```console
uv run uptimely explore
```

Open <http://127.0.0.1:8001/> in a browser. This command runs the local server
until you stop it.
