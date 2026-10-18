# `uptimely engine`

## `engine run`

Execute the plan in the project's last successful active build:

```console
uptimely engine run \
  [--project-root PATH] [--config PATH] [--verbose]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--project-root PATH` | No | Current working directory | Project root containing the active build and function entrypoints. |
| `--config PATH` | No | `config/engine.json` under the project root or current working directory | Engine settings and runtime bindings in JSON. |
| `--verbose` | No | `false` | Print execution stages and dataset registry details when enabled. |

Build or rebuild the project with `uptimely project build` to change its
execution plan or feature scope. Engine validates and executes the saved build
without compiling or generating artifacts. Missing or invalid builds report a
recovery command.

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
