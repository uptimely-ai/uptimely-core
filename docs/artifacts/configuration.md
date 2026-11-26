# Configuration file format

Uptimely project configuration files use TOML. The
[example project's `uptimely.toml`](https://github.com/uptimely-ai/uptimely-core/blob/main/example/uptimely.toml)
shows a complete configuration.

## Top level settings

The file supports these top-level tables:

| Table | Contents |
| --- | --- |
| `[application]` | Optional specification source settings. |
| `[code]` | Project code language, source directory, and requirements definition location. |
| `[engine]` | Engine settings, including the nested `[engine.backend]` table. |
| `[test]` | Project test folder. |
| `[paths]` | A flat table of path strings. |
| `[params]` | A flat table of scalar values. |

## All settings

Below is the full configuration file reference.

| Setting | TOML value | Default or constraint |
| --- | --- | --- |
| `application.python_spec` | String | Optional `MODULE:ATTRIBUTE` entrypoint. Mutually exclusive with other source settings. |
| `application.json_spec` | String | Optional project-root-relative or absolute JSON path. Mutually exclusive with other source settings. |
| `application.yaml_spec` | String | Optional project-root-relative or absolute YAML file or directory. Mutually exclusive with other source settings. |
| `code.language` | String | Code language. Only `"python"` is supported and it is the default. |
| `code.requirements` | String | Optional project-root-relative or absolute requirements definition file. If omitted, discover `requirements/pyproject.toml` or the project root's `pyproject.toml`. Overridden by the `requirements_file` argument to `Uptimely.build()`. |
| `code.src` | String | Optional project-root-relative or absolute source path used when building. The selected source is copied into the active build. |
| `test.path` | String | Nonempty project-root-relative or absolute test directory. Default: `"tests"`. |
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

Standalone build APIs accept a `uptimely.project.config.CodeSettings` object
through their `code` argument. Set the code language, definition path, and source
path on that object.
