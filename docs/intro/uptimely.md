# About Uptimely Core

The main inspiration for Uptimely is: *How to get thing x calculated with minimal effort*.

## Universal language for data science?

There is no universal declarative language to express arbitrary calculations in data analytics space.

Traditional mathematics offers limited support for representing and working with data and its structures.

SQL is the closest answer, because it standardizes the structure of the data. Modern systems allow Python inside SQL. Even in that case, a simple Python-procuded column might have went through plethora of processing steps, and SQL is fully unaware of those.

Year | Region | Sales | Python forecast
--- | --- | --- | ---
2024 | EU | 4 500 | NULL
2025 | EU | 5 100 | NULL
2026 | EU | NULL | 5 670
2027 | EU | NULL | 6 740

Everybody understands that the actual sales is simply sum of smaller numbers. But who knows how that Python forecast was created? And how data scientists keep it maintainable when it can be 10 000 lines of code without standards?

This is just one of the examples where traditional methods fall short with advanced data science.

## Design principles

The design starting point then became:

* What could be a standard atomic operation in data science?
* How to express it with minimal implementation-agnostic syntax?
* What is the most standard way of publishing reproducible steps?

## Where Uptimely draws the line

Uptimely starts from defining profiles containing set of features in defined grain and scope. Features are produced by operators that bind to functions that are able to produce the result. The operators are the atomic unit of data science.

This abstraction makes operators implementation agnostic. To reproduce the results, you need:

* The source code
* Language and version
* Code packages and versions

These are the artifacts that Uptimely publishes.

Uptimely does not say how these reproducible blueprints should be physically deployed or executed. The important things, is you get same results everywhere and understand how they were calcualted.

In addition to those artifacts, Uptimely provides a logical plan to materialize the results and tooling to validate that each operator binding returns the results it promises.
