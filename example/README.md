# Example project for Data center cooling pumps

This project uses synthetic telemetry for six cooling-system pumps across two
data centers and four server rooms. It demonstrates asset hierarchies,
time-based telemetry, and externally calculated measurements in an Uptimely
Core workflow.

Health scores, warning thresholds, and operating-point recommendations are
illustrative calculations.

## Analytical profiles

Profile is Uptimely's primary concept to organize data science in manageable components.

Each profile is declared in `spec/profiles/<profile_id>.py`.

| Profile | Purpose |
| --- | --- |
| `pump_telemetry` | Combines pump readings with asset metadata. |
| `pump` | Resolves capacity from the pump, series, then category and combines telemetry with external measurements. |
| `constants` | Provides physical constants for cooling pump analytics. |
| `pump_series` | Provides capacity metadata for pump series. |
| `pump_category` | Provides capacity metadata for pump categories. |
| `pump_telemetry_by_minute` | Summarizes maximum bearing temperature per pump and minute. |
| `pump_telemetry_by_hour` | Summarizes maximum bearing temperature per pump and hour. |
| `pump_telemetry_by_day` | Summarizes maximum bearing temperature per pump and day. |
| `pump_telemetry_when_warning` | Filters telemetry to warning readings. |
| `pump_telemetry_by_hour_when_warning` | Summarizes warning readings by hour and calculates an illustrative operating-point recommendation. |

The external workflow reads a sample CSV, calculates a measurement ratio, and
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

The heart of the project is in `spec/spec.py`. It combines analytical specification of functions, profiles, operators and dimension into a single Python object.

When a build is created the Python object is serialized to a json file. At the same time, a portable execution plan with resolved function arguments is generated. It can be consumed either by Uptimely's built-in engine, or deployed to any orcestrator that can execute Python functions.


## Build and run

Depending on the setup, use either of:

* `uptimely <command>`
* `uv run uptimely <command>`
* `poetry run uptimely <command>`

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
