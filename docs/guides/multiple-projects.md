
# Organizing analytics projects

## Start with a single standalone project

Keep the organization's full analytical system in a single project and
repository. This is simple to start with and keeps analytics easy to find and
access. It can scale far, but may eventually need to be split into multiple
projects.

## Multiple independent projects

### Full isolation

Keep multiple Uptimely projects fully independent. Each project owns its
specification, build, and runtime configuration. In a monorepo, projects share
a repository while remaining isolated. In a multirepo layout, each project has
its own repository.

<div class="project-layouts" role="img" aria-label="Monorepo and multirepo project layouts">
  <section class="project-layout" aria-label="Monorepo">
    <h4>Monorepo</h4>
    <div class="project-layout-flow">
      <div class="project-box">One repository</div>
      <b aria-hidden="true">&#8594;</b>
      <div class="project-boxes"><span>Project A</span><span>Project B</span></div>
    </div>
  </section>
  <section class="project-layout" aria-label="Multirepo">
    <h4>Multirepo</h4>
    <div class="project-layout-flow">
      <div class="project-boxes"><span>Repository A</span><span>Repository B</span></div>
      <b aria-hidden="true">&#8594;</b>
      <div class="project-boxes"><span>Project A</span><span>Project B</span></div>
    </div>
  </section>
</div>

For a small number of projects, keeping them fully independent makes the setup simple.

Some amount of code repetition across independent projects is acceptable. When the organization grows, share reusable Python functions through packages.

### Consolidating artifacts

In this approach builds from multiple independent projects are combined in deployment.
If needed, the master project can combine build artifacts such as specs, plans or explorer data to a centralized database.

Each project can build and publish its own artifacts.

<div class="project-flow" role="img" aria-label="Projects publish builds to shared artifact storage">
  <section class="project-box"><h4>Project A</h4><div class="calculation-box">Build A</div></section>
  <b aria-hidden="true">&#8594;</b>
  <div class="project-box">Shared artifact storage</div>
  <b aria-hidden="true">&#8594;</b>
  <section class="project-box"><h4>Project B</h4><div class="calculation-box">Build B</div></section>
</div>

Alternatively, the deployment pipeline can build artifacts on behalf of projects
that grant it repository access.

<div class="project-flow" role="img" aria-label="Deployment pipeline builds artifacts on behalf of projects">
  <section class="project-box"><h4>Deployment</h4></section>
  <b aria-hidden="true">&#8594;</b>
  <div class="project-boxes">
    <section class="project-box"><h4>Project A</h4><div class="calculation-box">Build A</div></section>
    <section class="project-box"><h4>Project B</h4><div class="calculation-box">Build B</div></section>
  </div>
  <b aria-hidden="true">&#8594;</b>
  <div class="project-box">Shared artifact storage</div>
</div>

At the moment Uptimely does not provide tooling to consolidate multiple projects, so this part is user's responsibility.


## Multiple dependent projects

Consider having foundational calculations that repeat in almost every data science project. For example: Whatever you calculate, you always need to first derive information about maintenance periods.

This needs to be done from data center pump measurements, because maintenance data is not integrated or is unreliable. The calculation logic varies by pump category, so you don't want to do this again in every project.

### Pattern 1: Persist in between

The "trivial" approach is to create a standalone project for maintenance detection only. The results are materialized to storage that other projects can read the results from.

In most cases this by far easiest solution.

Even if this sounds simple, Uptimely profiles might be helpful abstraction to get calculations right. Also, the explorer gives everyone up-to-date view on the calculation logic and documentation out of the box. Pretty much all analytical use cases in the whole organization become dependent on these results, so the interface must be seamless.

One possible downside is time penalty from extra write and read to database compared to calculating in-memory. Depending on the setup, two separate processing pipelines might have delays in between.

<div class="project-flow project-flow-data" role="img" aria-label="Multiple projects consume maintenance results from a database">
  <section class="project-box"><h4>Maintenance project</h4><div class="calculation-box">Maintenance detection</div></section>
  <b aria-hidden="true">&#8594;</b>
  <div class="project-box">Database</div>
  <b aria-hidden="true">&#8594;</b>
  <div class="project-boxes">
    <section class="project-box"><h4>Data science project 1</h4><div class="calculation-box">Neural network</div></section>
    <section class="project-box"><h4>Data science project 2</h4><div class="calculation-box">Clustering algorithm</div></section>
  </div>
</div>

### Pattern 2: Reuse the build

What if a data scientist needs to tweak the logic on maintenance detection to get their neural networks right? Or what if they notice that something smells wrong in the maintenance detection and need to verify without being dependent on other project or team?

In this case it is not enough to have just the maintenance detection results, but reusable calculations are needed. Both the functions, but also their argument bindings. You don't want to spend a week writing hundreds of lines of Python or SQL just to get to filter maintenance events from the data.

If the maintenance detection was created by Uptimely, it could publish its build artifacts to shared file storage.

Any other person or team can access the full chain of analytical operators and run it as they wish.

<div class="project-flow project-flow-data" role="img" aria-label="Multiple projects reuse maintenance detection from a published build">
  <section class="project-box"><h4>Maintenance project</h4><div class="calculation-box">Maintenance detection</div></section>
  <b aria-hidden="true">&#8594;</b>
  <div class="project-box">Published build</div>
  <b aria-hidden="true">&#8594;</b>
  <div class="project-boxes">
    <section class="project-box"><h4>Data science project 1</h4><div class="calculation-box">Modified maintenance detection</div><div class="calculation-box">Neural network</div></section>
    <section class="project-box"><h4>Data science project 2</h4><div class="calculation-box">Maintenance detection</div><div class="calculation-box">Clustering algorithm</div></section>
  </div>
</div>

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
    grain = [measurement_id.at("measurement_id")]
    seed = "read_values"

    assembly = [
        up.Operator(
            id="read_values",
            outputs=[up.Feature(id="value")],
            compute=up.Bind(read_values),
        ),
        up.Operator(
            compute=up.Bind(
                intermediate_step,
                dataset=up.ref.dataset(),
                output=up.ref.output("intermediate_result"),
            ),
        ),
        up.Operator(
            id="is_maintenance",
            compute=up.Bind(
                derive_maintenance,
                dataset=up.ref.dataset(),
                intermediate=up.ref.input("intermediate_result"),
                output=up.ref.output("is_maintenance"),
            ),
        ),
    ]


spec = up.Spec(
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
# example

import uptimely as up


spec = up.load_spec("shared-build/spec.json")
telemetry = spec.profiles["telemetry"]
del telemetry.assembly["is_maintenance"]
del telemetry.features["is_maintenance"]

updated_doc = "spec.json"
up.write_document(spec, updated_doc)

app = up.Uptimely()
bundle = app.build(updated_doc)
result = app.create_engine(bundle).run()

print(result.datasets["telemetry"])
```

The result contains `id`, `value`, and `intermediate_result`, without calculating
`is_maintenance`. The shared spec stays unchanged.

Now the data scientist can use the intermediate results for their work.
