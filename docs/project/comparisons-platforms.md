# How Uptimely fits with analytics platforms

## Data and analytics platforms

With platforms such as Snowflake, BigQuery, Databricks, and Dataiku, teams typically configure how calculations run, including compute, deployment, and programming languages.

Uptimely focuses on describing what information and calculations are needed. The mentioned systems act as possible calculation backends.

## Data transformation tools

Tools such as dbt are well suited to defining relationships between data models, cleaning data, and applying structural transformations.

Uptimely has many similar concepts than dbt, but is targeted to analytical calculations, Python-first ecosystem for data scientists.

## Feature stores

Feature stores help organizations serve, share, and version data for machine learning.

Uptimely would be possible data produces for feature store, whose primary purpose is to gather already computed data and serve it efficiently.

## Stateful engines

Engines such as Flink, Kafka Streams, Google Dataflow, and Spark Streaming could serve as stateful processing backends in the future. State abstraction is on the Uptimely Core roadmap, with the goal of making it possible to switch between backends.

## Orchestrators

The build bundle's execution plan contains dependency-ordered function invocations.
These can be deployed to orchestrators with or without the Uptimely engine.

## Jupyter notebooks

Data scientists typically use Jupyter notebooks to research new algorithms and,
when useful, explore and debug code.

Parts of Uptimely can run in notebooks, but the framework is primarily designed
for software projects running in production.

Uptimely's semantic model and feature-subset execution help researchers access
the same data definitions and calculations used in production, reducing the gap
between experimentation and implementation.
