# Feature dependency graph

Data teams might have various lineages to visualize data flow:

* Dimensional model for data warehouses
* ETL data flow
* Analytical task executions
* Machine learning infrastructure

All of these are physical-level visualizations of data, but they often do not reveal how results are consumed by end users or which logical features depend on one another.

## Demo

![Isolated analytical calculations](https://uptimely-public.s3.pl-waw.scw.cloud/uptimely-demo/uptimely-core/standalone-function-logical-model.png)

Here is another example screenshot from a logical model. Red diamonds are functions, blue circles are features.

The left cluster is a standalone optimization that shares no input or output variables with the rest of the analytical flow. It still interacts with the same database table physically.

## Column-level lineage in Python

Tools like `dbt` support [column-level lineage](https://docs.getdbt.com/docs/explore/column-level-lineage?version=2), but that does not work with Python. From the dbt website:

> Python error — Error occurs when a Python model is used within the lineage. Due to the nature of Python models, it's not possible to parse and determine the lineage.

This framework aims to fill that gap in the tooling.

## Subsetting by feature

A subset can be sliced from the global graph. This is useful for on-demand calculation, debugging, documentation, or isolated processing for a single feature.

## Difference between physical and logical lineage

Physical data shows stored values, but does not necessarily explain their
analytical meaning. Consider two features observed at two steps:

| Step | Feature | Value |
| --- | --- | --- |
| 1 | A | 10 |
| 1 | B | 8 |
| 2 | A | 11 |
| 2 | B | 17 |

These rows do not tell a consumer what `A` and `B` represent, how they were
produced, or which downstream calculations use them. The same values can support
different business definitions, reports, and decisions.

Suppose calculated feature `B` depends on feature `A`.

The Python processing might look clear:

`python_function_for_b(a)`

But in practice, you need to inspect a lot of code before you understand the whole system:

* What data type is `a`?
* If it is a standard DataFrame, what schema does it have?
* Are the documentation and docstrings up to date?
* Is the function reading additional data?
* Is the function generating additional features?
* Where is the business logic in the function?
* Does the function have side effects?
* What are the dependencies for `A`?

Or maybe they are produced in a single black-box execution named `process_many_things`.

The [specification](../specification/index.md) provides a logical layer alongside
the physical data by declaring feature identities, dependencies, and the
operations that produce them. The feature dependency graph visualizes those
declarations, connecting source inputs to consumption-ready information without
requiring consumers to reconstruct the workflow from database tables and
implementation code.

The graph distinguishes two kinds of features: green circles are columns supplied by fragments, blue circles are calculated features, and orange cylinders are functions.
