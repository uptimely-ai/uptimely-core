# `uptimely engine`

## `engine run`

Compile and execute an analytics workflow, or execute a previously saved plan:

```console
uptimely engine run \
  [--project-root PATH] [--spec PATH] [--features NAME ...] \
  [--compile {true,false}] [--plan PATH] [--config PATH] [--verbose]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--project-root PATH` | No | Current working directory | Root for resolving default paths and importing function entrypoints. |
| `--spec PATH` | No | `_generated/spec/spec.json` under the project root or current working directory | Spec JSON input when compiling. |
| `--features NAME ...` | No | All features | Select output features and their dependencies when compiling. |
| `--compile {true,false}` | No | `true` | Compile spec before execution, or load a saved plan with `false`. |
| `--plan PATH` | No | `_generated/compile/execution_plan.json` under the project root or current working directory | Saved plan JSON to load. Requires `--compile false`. |
| `--config PATH` | No | `config/engine.json` under the project root or current working directory | Engine settings and runtime bindings in JSON. |
| `--verbose` | No | `false` | Print execution stages and dataset registry details when enabled. |

When `--compile false` is used, `--spec` and `--features` are not accepted.
The engine configuration has a `backend` object validated as `EngineConfig`
and a `bind` object for runtime values:

```json
{
  "backend": {},
  "bind": {}
}
```

See the [execution engine specification](../../components/engine.md) for
backend settings and runtime overrides.
