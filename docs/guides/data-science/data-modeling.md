# Data Modeling and Uptimely

Data modeling gives data structure and meaning by defining what it represents,
how its elements relate, and at what level of detail it is recorded.

Let's first take a short recap on dimension modeling, and then see how Uptimely applies decades of best practices to the era of data science and AI.

## Dimensional modeling

Dimensional modeling organizes data around business processes, facts, and
dimensions. A fact table has a defined **grain**: what one row represents.
For example, one row might represent one cooling-pump measurement at one timestamp.

A dimensional model can cover an entire organization or a single business
process. It describes the data and its organization. But leaves open how data is calculated into those structures.

SQL is commonly used to query and
transform warehouse data, but it is not a requirement of dimensional
modeling.

See Kimball's explanation of [fact-table grain](https://www.kimballgroup.com/2008/11/fact-tables/).

## Fact-table shapes

The same measurements can be represented in different table shapes. In a
long-format table, each row records one measurement. Its grain is one machine,
date, and measurement:

| Machine | Machine Category | Date | Measurement | Value |
|---|---|---|---|---:|
| M001 | Category A | 2026-01-01 | Runtime | 20 |
| M001 | Category A | 2026-01-01 | Energy | 150 |
| M002 | Category A | 2026-01-01 | Runtime | 22 |
| M002 | Category A | 2026-01-01 | Energy | 165 |
| M101 | Category B | 2026-01-01 | Runtime | 18 |
| M101 | Category B | 2026-01-01 | Energy | 130 |
| M101 | Category B | 2026-01-01 | Downtime | 52 |

The same data can be represented in wide format, with one column per
measurement. Here the grain is one machine and date:

| Machine | Machine Category | Date | Runtime | Energy | Downtime |
|---|---|---|---:|---:|---:|
| M001 | Category A | 2026-01-01 | 20 | 150 | NULL |
| M002 | Category A | 2026-01-01 | 22 | 165 | NULL |
| M101 | Category B | 2026-01-01 | 18 | 130 | 52 |

Each shape serves different storage and use needs.

The advantage of long format is consistent schema and dense data population. Wide format on the other hand is better for calculations requiring multiple metrics from the same grain.

## Uptimely profile describes analytical calculation model

Data such as data center cooling-pump telemetry can have several
analytical views. This is what Uptimely **profiles** are for: An analytical model whose dataset is has in specific grain.

What often might be a fact table in dimensionaly modeled data warehouse, would be multiple profile datasets in Uptimely's model. You can think it as a subset or a view of a physical fact table.

You might have a profile for cooling pumps in category A:

| Machine | Machine Category | Date | Runtime | Energy | Downtime |
|---|---|---|---:|---:|---:|
| <span class="dm-profile-selected">M001</span> | <span class="dm-profile-selected">Category A</span> | <span class="dm-profile-selected">2026-01-01</span> | <span class="dm-profile-selected">20</span> | <span class="dm-profile-selected">150</span> | NULL |
| <span class="dm-profile-selected">M002</span> | <span class="dm-profile-selected">Category A</span>| <span class="dm-profile-selected">2026-01-01</span> | <span class="dm-profile-selected">22</span> | <span class="dm-profile-selected">165</span> | NULL |
| M101 | Category B | 2026-01-01 | 18 | 130 | 52 |

And another profile for cooling pumps in category B:

| Machine | Machine Category | Date | Runtime | Energy | Downtime |
|---|---|---|---:|---:|---:|
| M001 | Category A | 2026-01-01 | 20 | 150 | NULL |
| M002 | Category A | 2026-01-01 | 22 | 165 | NULL |
| <span class="dm-profile-selected">M101</span> | <span class="dm-profile-selected">Category B</span> | <span class="dm-profile-selected">2026-01-01</span> | <span class="dm-profile-selected">18</span> | <span class="dm-profile-selected">130</span> | <span class="dm-profile-selected">52</span> |

They have same grain, but different row scope and feature set.

Uptimely profiles are more than data. They describe how the data was produced to the dataset by analytical **operators**.

## Data Vault and Uptimely

Data Vault and Uptimely address different problems. Data Vault structures
enterprise data to integrate information from changing source systems and
preserve its history. Uptimely defines and runs analytical calculations over
data. It does not provide a Data Vault or replace a data-integration and
storage architecture.

They can be used in the same organization, but are not alternatives: a data
platform may use Data Vault to manage source history and use Uptimely for
calculations that serve operational or analytical needs.
