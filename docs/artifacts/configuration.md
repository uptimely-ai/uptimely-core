# Configuration file format

Uptimely project configuration files use TOML. The
[example project's `uptimely.toml`](https://github.com/uptimely-ai/uptimely-core/blob/main/example/uptimely.toml)
shows a complete configuration.

## Top level settings

The file supports these top-level tables:

| Table | Contents |
| --- | --- |
| `[application]` | Optional specification source and source directory settings. |
| `[runtime]` | Location of the runtime dependency definition for builds. |
| `[engine]` | Engine settings, including the nested `[engine.backend]` table. |
| `[paths]` | A flat table of path strings. |
| `[params]` | A flat table of scalar values. |

## All settings

Below is the full configuration file reference.

| Setting | TOML value | Default or constraint |
| --- | --- | --- |
| `application.python_spec` | String | Optional `MODULE:ATTRIBUTE` entrypoint. Mutually exclusive with `application.json_spec`. |
| `application.json_spec` | String | Optional project-root-relative or absolute path. Mutually exclusive with `application.python_spec`. |
| `application.src_path` | String | Optional project-root-relative or absolute source path used when building. The active build saves the resolved selection for later runs. |
| `runtime.path` | String | Project-root-relative or absolute directory. Default: `"runtime"`. Overridden by the `runtime_path` argument to `Uptimely.build()`. |
| `engine.preview_rows` | Integer | Positive integer. Default: `5`. |
| `engine.backend.type` | String | Default: `"python_venv"`. |
| `engine.backend.definition` | String | Optional. |
| `engine.backend.dataframe` | String | Default: `"polars"`. |
| `engine.backend.evaluation` | String | Default: `"eager"`. |
| `engine.backend.batch_size` | Positive integer or `"*"` | Optional. |
| `[paths]` entries | String | Flat table with Python-identifier keys. |
| `[params]` entries | String, integer, float, or boolean | Flat table with identifier-style keys. |

For loading, precedence, and runtime behavior, see
[Configure a project](../guides/configuration.md).
