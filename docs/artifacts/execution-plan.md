# Execution plan

The execution plan is the versioned `plan.json` build artifact. It records
function calls, their optional semantic metadata, and their execution order.
It does not contain function implementations.

The Engine executes explicit calls with optional analytical validation. Targeted
execution is not currently supported.

## Structure

This example shows the call structure and omits the required `plan_version`.

```json
{
  "required_backend": "polars",
  "invocations": [
    {
      "id": "read",
      "entrypoint": "pump_io:read",
      "arguments": {"path": "$paths.input"},
      "returns": "$datasets.pump.read"
    },
    {
      "id": "derive",
      "entrypoint": "pump_io:derive",
      "arguments": {"dataset": "$datasets.pump.read"},
      "returns": "$fragments.pump.derive"
    },
    {
      "id": "merge",
      "entrypoint": "pump_io:merge",
      "arguments": {
        "dataset": "$datasets.pump.read",
        "fragment": "$fragments.pump.derive"
      },
      "returns": "$dataset.pump.derive"
    }
  ],
  "stages": [["read"], ["derive"], ["merge"]],
  "datasets": {"pump": "$dataset.pump.derive"}
}
```

Each invocation declares `id`, `entrypoint`, `arguments`, and `returns`.

Each non-null `returns` value defines an invocation result. Compute-only calls
use `$datasets.<profile>.<operator>`, compute calls with a merge use
`$fragments.<profile>.<operator>`, and merge calls use
`$dataset.<profile>.<operator>`. Return names are unique across the plan and
cannot be overwritten.

## Arguments

Arguments are JSON values. Strings can refer to runtime values, including
inside arrays and objects:

- `$datasets.<profile>.<operator>`, `$fragments.<profile>.<operator>`, and
  `$dataset.<profile>.<operator>` refer to named returns from earlier calls.
- `$params.<name>` refers to a runtime parameter.
- `$paths.<name>` refers to a runtime path.

These prefixes are reserved for references, including when a string has the
same text as a reference. Other strings are literals. Parameter and path names
must be identifiers and must be present at runtime. A relative path is resolved
against the project root. Missing returns are errors. To pass an absent initial
dataset, use null. A returned null remains a valid value. Named returns can
also contain values other than dataframes.

`datasets` maps human-readable final dataset names to result references. The
mapping creates aliases and does not change or overwrite the underlying values.

## Stages and semantics

Every invocation occurs once in `stages`. Invocations run in stage order and in
the listed order within each stage. A return must be produced before it is
referenced. The compiler orders calls, including side effects.
Explorer topology shows compiler dependencies derived from the Spec. These can
differ from dataframe references in invocation arguments.

The optional `semantics` field carries an analytical contract for validation and
provenance. An executor offering analytical validation must report missing
contracts rather than silently skip validation.

## Versioning

`plan_version` identifies the format of `plan.json`, independently of the Spec
format. A runtime accepts only the plan version it supports and does not migrate
older plans.

## Learn more

See the [Compiler](../concepts/compiler.md), the [Engine](../concepts/engine.md),
and the [plan models](../python/plans-models.md).
