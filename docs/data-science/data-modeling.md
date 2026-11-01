# Data Modeling and Uptimely

Data models organize business data so people can understand and use it.
Uptimely describes calculation-facing datasets and the features and
dependencies that make up analytical workflows. These are complementary
concerns: Uptimely can use data from different modeling approaches without
requiring a one-to-one match between stored tables and analytical datasets.

## Dimensional modeling

Dimensional modeling organizes data around business processes, facts, and
dimensions. A fact table has a defined **grain**: what one row represents.
For example, one row might represent one pump measurement at one timestamp.

A dimensional model can cover an entire organization or a single business
process. It describes the data and its organization; it does not prescribe
how every calculation must be implemented. SQL is commonly used to query and
transform warehouse data, but it is not a requirement of dimensional
modeling.

See Kimball's explanation of [fact-table grain](https://www.kimballgroup.com/2008/11/fact-tables/).

## Fact-table shapes

The same measurements can be represented in different table shapes. In a
long-format table, each row records one measurement. Its grain is one machine,
date, and measurement:

| Machine | Machine Family | Date | Measurement | Value |
|---|---|---|---|---:|
| M001 | Family A | 2026-01-01 | Runtime | 20 |
| M001 | Family A | 2026-01-01 | Energy | 150 |
| M002 | Family A | 2026-01-01 | Runtime | 22 |
| M002 | Family A | 2026-01-01 | Energy | 165 |
| M101 | Family B | 2026-01-01 | Runtime | 18 |
| M101 | Family B | 2026-01-01 | Energy | 130 |

The same data can be represented in wide format, with one column per
measurement. Here the grain is one machine and date:

| Machine | Machine Family | Date | Runtime | Energy |
|---|---|---|---:|---:|
| M001 | Family A | 2026-01-01 | 20 | 150 |
| M002 | Family A | 2026-01-01 | 22 | 165 |
| M101 | Family B | 2026-01-01 | 18 | 130 |

Each shape serves different storage and use needs. A wide, calculation-facing
view can be selected or reshaped from dimensional tables; it does not have to
be the warehouse's physical storage format.

## Data Vault and Uptimely

Data Vault is a data-modeling approach for integrating and historizing
enterprise data. It organizes information into Hubs, Links, and Satellites;
Uptimely does not replace these structures or prescribe how data is stored.
Instead, Uptimely can define analytical datasets and feature calculations
that use data sourced from a Data Vault. The Vault's structures and Uptimely
datasets serve different purposes and need not correspond one-to-one.

## Uptimely datasets describe analytical views

An entity is an analytical subject, such as a pump or production line. An
Uptimely dataset describes a view of that entity: the rows in scope, their
grain, and the features available at that scope. One entity can have separate
datasets for minute-level telemetry, daily summaries, or maintenance events.

A dataset is not necessarily a physical table. It can select rows and
features from one fact table or combine data from several tables.

For example, warehouse telemetry for a factory could support minute-level
measurements for a production line and hourly summaries for individual pumps.
These datasets have different row scopes and grains even if they draw on the
same underlying warehouse tables.

Uptimely processes features in a wide, calculation-facing form. For instance,
the wide fact table above could supply a dataset for Family A:

| Machine | Date | Runtime | Energy | Downtime |
|---|---|---:|---:|---:|
| M001 | 2026-01-01 | 20 | 150 | 45 |
| M002 | 2026-01-01 | 22 | 165 | 67 |

It could also supply a Family B dataset with a different set of features:

| Machine | Date | Runtime | Energy |
|---|---|---:|---:|
| M101 | 2026-01-01 | 18 | 130 |

The `Downtime` feature, for example, could be calculated rather than stored
in the source fact table. A dataset can also use a different grain from the
physical tables that supply it.

## Organizing calculations by dataset

Features with the same name are not always calculated the same way in every
dataset. An industrial company might want to calculate operating modes or
detect overheating for different kinds of machines. A request such as "raise
an alarm for high temperature" names a business goal, but does not specify
whether it uses an existing signal, a straightforward calculation, or a
model.

For example, `Energy` for one machine family might be a directly available
measurement, while another family's value requires a specialized calculation.
Putting all such behavior into one broad calculation can obscure differences
in row scope, machine behavior, and business rules.

Uptimely describes each calculation in the dataset where its inputs and
behavior make sense. Datasets can share reusable functions when their
implementations are genuinely common, while keeping different calculations
distinct when their logic differs. This makes the analytical organization
explicit without requiring the source data model to encode every
calculation-specific variation.

## How the two approaches fit together

A data model explains how source data is organized. An Uptimely specification
describes the calculation-facing datasets and features built from that data.
For example, one dimensional fact table can support multiple datasets, and
one dataset can combine multiple tables; neither needs a one-to-one
correspondence.

Uptimely's declared dimensions identify dataset rows and can reflect keys in
the source model. The framework can check that calculation results contain
the expected dimension columns and types, have no duplicate dimension keys,
and preserve input keys where required. These structural checks do not
establish that a formula is analytically correct; domain review and result
tests are still necessary.

For how SQL fits into the implementation and workflow around calculations,
see [Comparison to SQL](comparison-to-sql.md).
