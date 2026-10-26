# Difference to dimensional modeling

Dimensional modeling and Uptimely solve related but different problems.
Dimensional modeling organizes data for analysis. Uptimely describes
analytical features and, most importantly, the dependencies between them.

## The fundamental difference

A Kimball fact table models measured business events at a declared grain.
An Uptimely dataset defines the rows and features that an analytical
calculation works with. They are not equivalent: one fact table can supply
multiple Uptimely datasets, and a dataset can combine data from multiple
tables.

## What dimensional modeling describes

A dimensional model organizes data around business processes, facts, and
dimensions. A fact table has a defined **grain**: what one row represents.
For example, a row might represent one pump measurement at one timestamp.

A model can cover an entire organization or just one business process.
Warehouse teams often use SQL to query and transform this data, but SQL is
not a requirement of dimensional modeling. The model describes the data;
it does not prescribe how every calculation must be implemented.

See Kimball's explanation of [fact-table grain](https://www.kimballgroup.com/2008/11/fact-tables/).

## What Uptimely describes

Uptimely primarily describes analytical features and what each feature depends
on, including other features. This dependency graph shows how the analytical
system fits together and what must be available to produce a result.

Functions define the calculation steps that produce or transform features.
They are important, but the main focus is the feature dependencies—not the
implementation details of each function. Features can be identified from a
dimensional model. Uptimely builds on that model; it does not replace it.

The distinction is one of focus:

- A dimensional model describes how data is organized.
- An Uptimely spec describes which analytical features are needed and how
  they depend on one another.

## One source, multiple datasets

An Uptimely dataset describes an analytical view of data. It defines a row
scope, a grain, and the features available at that grain. It does not have to
correspond to a separate physical table.

For example, data warehouse telemetry for a factory could support:

- Minute-level measurements for a production line.
- Hourly summaries for individual pumps.

These are different analytical datasets even if they use the same underlying
source and dimensions. Each has its own row scope and useful features.

## Calculation and validation

Uptimely uses declared dimensions to validate the structure of analytical
data. These dimensions can reflect the dimensional model: they identify the
rows in a dataset and provide keys for relating feature values. For example,
the framework can check that calculation results include the expected
dimension columns, have valid dimension types, and do not contain duplicate
dimension keys. A vectorized calculation must also preserve its input keys.

This lets Uptimely catch structural mismatches at calculation boundaries
without dictating how calculations work internally. Function implementations
remain user-defined. Structural checks do not prove that a formula is
analytically correct; domain review and result testing are still needed.
