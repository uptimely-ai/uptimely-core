# Analytics project structure

This page shows a recommended project layout for a single analytics project built with Uptimely Core.

## Suggested structure

A practical setup keeps source data, spec declarations, runtime configuration
and generated artifacts separate:

```text
project/
├── data/
├── functions/
│   └── analytics.py
├── config/
│   └── config.json
├── spec/
│   ├── spec.py <-- default spec entrypoint
│   ├── dataset_<name>.py
│   ├── entity.py
│   └── dimension.py
└── _generated/
    └── build/
        ├── build.json
        ├── spec.json
        ├── execution_plan.json
        └── explorer/
```

## Folder responsibilities

| Path | Responsibility |
| --- | --- |
| `data/` | Raw or reference datasets used by the analytics workflow. |
| `functions/` | Reusable source, calculation, and write functions. |
| `spec/` | The project specification: either Python declarations or a JSON document. |
| `_generated/` | Generated project artifacts. The active build is stored in `_generated/build/`. |
| `config/config.json` | Engine backend settings under `engine` and required global scalar values under `params`, referenced by `$params.<name>`. |

This separation keeps the project easy to reason about: specification declarations
live in `spec/`, runtime logic lives in functions, and generated resources stay
clearly separate from source inputs.

Python dataset modules subclass `uptimely.spec.python.Dataset` and declare
`Action` objects under `producers`, `publishers`, and `pipelines`. Each action
points directly to an implementation in `functions/`, binds its arguments, and
defines its output features. See
[Python authoring](../python/python.md) for the declaration syntax.

## Building the project

`uptimely build <project>` reads `spec/spec.py` or `spec/spec.json` and generates
the build bundle shown above. If both sources exist, select one with
`--python-spec` or `--json-spec`. Rebuild after source changes: execution and
Explorer use the saved bundle rather than regenerating it.

See the [CLI reference](../cli/index.md) for build options and the
[pump analytics example](https://github.com/uptimely-ai/uptimely-core/tree/main/examples/pump_analytics)
for a runnable project. For structures spanning multiple projects or repositories, see
[organizing analytics projects](organize.md).
