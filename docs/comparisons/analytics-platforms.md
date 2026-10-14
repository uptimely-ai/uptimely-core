# How Uptimely fits with analytics platforms

## Data and analytics platforms

With platforms such as Snowflake, BigQuery, Databricks, and Dataiku, teams typically configure how calculations run, including compute, deployment, and programming languages.

Uptimely focuses on describing what information and calculations are needed. The mentioned systems act as calculation backends.

## Data transformation tools

Tools such as dbt are well suited to defining relationships between data models, cleaning data, and applying structural transformations. Uptimely complements this work by organizing reusable analytical functions and their dependencies across the broader analytical system.

## Feature stores

Feature stores help organizations serve, share, and version data for machine learning. Uptimely Platform is designed to integrate with existing feature stores so features can stay reusable and consistent across analytical functions.

## Stateful engines

Engines such as Flink, Kafka Streams, Google Dataflow, and Spark Streaming could serve as stateful processing backends in the future. State abstraction is on the Uptimely Core roadmap, with the goal of making it possible to switch between backends.

## Orchestrators

The framework currently includes a simple built-in runtime. Planned integrations include Airflow, Dagger, Flyte, and Snowflake tasks; expressing what to calculate can make plans straightforward to submit to orchestration tools.

## Jupyter notebooks

Notebooks are convenient for research and demos, but can be difficult to deploy, monitor, and scale in production. Uptimely sees notebooks as a valuable research tool rather than a production deployment model.
