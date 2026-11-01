# Comparison to SQL

SQL and Uptimely can both be part of an analytical workflow, but they serve
different roles. SQL is useful for querying and transforming data in a
warehouse. Uptimely is Python-first and describes how analytical features
relate to one another across datasets and calculations.

## SQL remains useful

Many calculations described in Uptimely can also be implemented in SQL.
Teams can use SQL to retrieve source data, transform it in place, or perform
calculations supported by their database.

Uptimely does not replace SQL. It can fit alongside SQL in the same workflow,
with the choice of where to query or transform data depending on the project
and its execution environment.

## From queries to feature dependencies

SQL is declarative: a query describes the requested result, and the database
chooses how to execute it. A SQL client can run successive queries and inspect
their intermediate results.

SQL itself does not require a project to declare how named analytical
features depend on one another across queries and datasets. Other tools can
provide orchestration or lineage, while Uptimely makes feature dependencies
part of the specification. This makes the relationships between calculations
explicit and inspectable.

Uptimely describes those dependencies, but leaves calculation implementations
user-defined. Its dataframe backends can accumulate operations into a plan
that the backend may optimize for execution.

## Testing and analytical correctness

SQL does not prescribe a complete workflow for organizing calculations,
testing domain-specific correctness, or validating changes. Teams can supply
these practices with SQL testing frameworks and other tools.

Uptimely provides structure for analytical features and their dependencies.
Structural checks can catch issues such as unexpected dataset dimensions, but
they cannot prove that a formula is correct. Domain review and result tests
remain important. For details on dataset shape and dimension checks, see
[Data Modeling and Uptimely](data-modeling.md).
