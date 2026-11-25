# Example project for Data center cooling pumps

The Uptimely Core [example project](https://github.com/uptimely-ai/uptimely-core/tree/main/example) uses synthetic telemetry for six cooling-system pumps across two
data centers and four server rooms. It demonstrates asset hierarchies,
time-based telemetry, and externally calculated measurements in an Uptimely
Core workflow.

Health scores, warning thresholds, and operating-point recommendations are
illustrative calculations.

## Analytical profiles

Profile is Uptimely's primary concept to organize data science in manageable components.

Each profile is declared in `spec/profiles/<profile_id>.py` or in a package at
`spec/profiles/<profile_id>/` when its features and profile declaration need
separate modules.
Each profile names a seed operator that initializes its dataset, either by
reading data or by transforming another profile.

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
| `tests/uptimely/` | Provisional JSON input and expected output cases for non-I/O compute bindings. |
| `uptimely.toml` | Project defaults, Engine settings, and configured input and output paths. |
| `config/production.toml` | Production overrides for the project configuration. |
| `artifacts/` | The active build, Explorer snapshot, and latest run and test metadata, including test case data. |

## Entrypoint

The heart of the project is in `spec/spec.py`. It combines analytical specification of functions, profiles, operators and dimension into a single Python object.

## Build and run

When a build is created the Python object is serialized to a specification file in json format.

At the same time, a portable execution plan with resolved function arguments is generated. It can be consumed either by Uptimely's built-in engine, or deployed to any orcestrator that can execute Python functions.


## Try yourself

Follow the steps in Uptimely Core readme or in documentation quick start to build, run and explore the project.
