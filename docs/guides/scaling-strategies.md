# Scaling strategies

Uptimely Engine runs functions defined in the execution plan and is not aware of where it runs. Optional runtime validation may execute lazy queries multiple times.

Even with this setup Uptimely gives plenty of opportunities to scale up from the basics.

## Use external execution backends

**Recommnedation: Use external auto scaling backend only when basic single worker setup is not sufficient.**

When Pandas was pretty much the only available dataframe implementation, it was easy to think that dataframe processing is limited by executor's memory.

In modern times dataframes are logical data operation representations that are capable of lazily accumulating execution plan until the result must be evaluated. For example, when the results need to persisted back to database.

Snowflake, BigQuery and Databricks (Spark) provide dataframe implementations that leverage automatic scaling of the external cluster, and the executor where Uptimely runs just collects the results.

The downside could be that the backend infra and dataframe implementation are coupled. It might be more difficult or impossible to debug the workflow locally.

Currently Uptimely requires that the logical operators are bound to functions that receive and return Polars dataframes. But inside the function, it is possible to do heavy lifting with other tooling than Polars.

!!! info "Planned dataframe interoperability"

    Uptimely has plans to support other user-configured dataframe
    implementations. Because users's define the calculation logic inside functions, Uptimely only needs to know which Python classes represent dataframes to validate function signatures.

    Engine just executes functions in the plan, and it only needs to understand which objects are Dataframes. According to roadmap, only required Dataframe specific operation would be conversion to Arrow format to standardize the result validation.

## Parallel engines

**Recommnedation: Use parallel engines when automatic scaling is not automatic or you want to use dataframe implemention indpendent of execution backend.**

Splitting a project into smaller projects and profiles is a straightforward way to keep execution units small.

A profile remains one logical definition even when its data is processed by
multiple Engine instances. For example, an external orchestrator can run the
same build on 100 subsets of 1 million pumps. The prerequisite is that each pump can be computed independently.

This case is applicable when the cluster resources are not scaled automatically, or you want to decouple backend infra from dataframe implementation.

### Configure partitioned execution

In the YAML spec, bind `start_id` and `end_id` params to the read function.

For example, bind a source function in its operator:

```yaml
assembly:
  read_pumps:
    function: project_io:read_pumps
    args:
      start_id: "$params.start_id"
      end_id: "$params.end_id"
```

In project configuration: Define common settings in `uptimely.toml`.
The orchestrator supplies a named config for each worker. For example,
`config/worker-000.toml` overrides the first worker's parameters:

```toml
[params]
start_id = 0
end_id = 10000
```

The Engine resolves these parameters when invoking the bound functions.
The parameters do not filter data automatically.

**Output functions:** Write each partition to a distinct database partition
or object. Configure any output path with a worker-specific `[paths]`
override, or pass a partition identifier to the output function.

**Worker environment:** Build once, then provide every worker with the same
saved build, common configuration, input access, and dependencies. Give each
worker an isolated project root because runs replace `artifacts/run/`.
Place its named config under that root's `config/` directory.

### Run 100 partitions

The orchestrator starts each worker with its own project root and config, for
example:

```console
uptimely run /workers/worker-000 --config worker-000
uptimely run /workers/worker-001 --config worker-001
```

These are separate processes running the complete saved plan on the configured
inputs. After all 100 runs succeed, the orchestrator checks that every partition
is present and combines or exposes their outputs as one logical profile. It
must track failures and retry missing partitions. Uptimely does not currently
create partitions, schedule workers, or combine their results.
