
# Organizing analytics projects

## A standalone project

Keep the organization's full analytical system in a single project and
repository. This is simple to start with and keeps analytics easy to find and
access. It can scale far, but may eventually need to be split into multiple
projects.

## Multiple independent projects

Keep multiple independent Uptimely projects in one or more repositories.
Each project contains its independent spec definition and builds.

For a small number of projects, some amount code repetition might win the overhead of maintaining centralized code packaging.

When the organization grows, share reusable Python functions through packages. Overriding per project is still possible. Keep each projects build bundle and execution results separate.

## Consolidate multiple specs

Each project or repository owns its analytical code and publishes a versioned JSON spec
partial. In this setup, projects just author the spec without executing the code.

A master project combines the spec json partials into one big spec json, exposing
cross-repository dependencies through agreed profile and feature identifiers.
Validate the complete document after merging and reject conflicting definitions.

Record contributing repositories and artifact versions alongside the assembled
spec, rather than maintaining a hand-edited copy of every team's declarations.
Publishing JSON does not require distributing implementation code, but executing
the combined workflow still requires callable implementations or wrappers.


## Multiple dependent projects

Consider having foundational calculations that repeat in almost every data science project. For example: Whatever you calculate, you always need to first derive information about maintenance periods.

This needs to be done from data center pump measurements, because maintenance data is not integrated or is unreliable. The calculation logic varies by pump category, so you don't want to do this again in every project.

### Pattern 1: Persist in between

The "trivial" approach is to create a standalone project for maintenance detection only. The results are materialized to storage that other projects can read the results from.

In most cases this by far easiest solution.

Even if this sounds simple, Uptimely profiles might be helpful abstraction to get calculations right. Also, the explorer gives everyone up-to-date view on the calculation logic and documentation out of the box. Pretty much all analytical use cases in the whole organization become dependent on these results, so the interface must be seamless.

One possible downside is time penalty from extra write and read to database compared to calculating in-memory. Depending on the setup, two separate processing pipelines might have delays in between.

### Pattern 2: Share the spec

What if a data scientist needs to tweak the logic on maintenance detection to get their neural networks right? Or what if they notice that something smells wrong in the maintenance detection and need to verify without being dependent on other project or team?

In this case it is not enough to have just the maintenance detection results, but reusable calculations are needed. Both the functions, but also their argument bindings. You don't want to spend a week writing hundreds of lines of Python or SQL just to get to filter maintenance events from the data.

If the maintenance detection was created by Uptimely, it could publish its build artifacts to shared file storage.

Any other person or team can access the full chain of analytical operators and run it as they wish.

Save this maintenance detection specification as `spec/spec.py` in the shared
project:

```python
# script

import polars as pl
import uptimely as up


def read_values() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": [1, 2],
            "value": [10, 20],
        }
    )


def intermediate_step(dataset: pl.LazyFrame, output: str) -> pl.LazyFrame:
    random_value = pl.int_range(0, pl.len()).shuffle()
    return dataset.with_columns(random_value.alias(output))


def derive_maintenance(dataset: pl.LazyFrame, intermediate: str, output: str) -> pl.LazyFrame:
    return dataset.with_columns((pl.col(intermediate) > 0.5).alias(output))


measurement_id = up.Dimension(
    id="measurement_id",
    resolutions=[up.Resolution(id="measurement_id", key="id", type="integer")],
)


class Telemetry(up.Profile):
    grain = [measurement_id.resolution("measurement_id")]
    seed = "read_values"

    assembly = [
        up.Operator(
            id="read_values",
            outputs=[up.Feature(id="value")],
            compute=up.Bind(read_values),
        ),
        up.Operator(
            outputs=[up.Feature(id="intermediate_result")],
            compute=up.Bind(
                intermediate_step,
                dataset=up.ref.dataset(),
                output=up.ref.feature("intermediate_result"),
            ),
        ),
        up.Operator(
            id="is_maintenance",
            outputs=[up.Feature(id="is_maintenance")],
            compute=up.Bind(
                derive_maintenance,
                dataset=up.ref.dataset(),
                intermediate=up.ref.feature("intermediate_result"),
                output=up.ref.feature("is_maintenance"),
            ),
        ),
    ]


python_spec = up.Spec(
    profiles=[Telemetry],
    name="Analytics Specification",
)
```

The build artifacts are created from command line:

```sh
uptimely build
```

Then the files need to be published to accessible storage location.

The Python modules referenced by its spec must also be importable, for example through an
installed package containing the shared implementation code.

Load the spec and remove both the `is_maintenance` operator and its feature
declaration. Save the edited spec temporarily to `spec.json`,
build it, and run its engine:

```python
# script

import uptimely as up


spec = up.load_spec("shared-build/spec.json")
telemetry = spec.profiles["telemetry"]
del telemetry.assembly["is_maintenance"]
del telemetry.features["is_maintenance"]

updated_doc = "spec.json"
up.write_document(spec, updated_doc)

app = up.Uptimely()
bundle = app.build(updated_doc)
result = app.create_engine(bundle).run(validate=True)

print(result.datasets["telemetry"])
```

The result contains `id`, `value`, and `intermediate_result`, without calculating
`is_maintenance`. The shared spec stays unchanged.

Now the data scientist can use the intermediate results for their work.
