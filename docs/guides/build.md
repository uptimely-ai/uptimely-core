# Build a project

### Specification source discovery

Without a source setting in `uptimely.toml` or CLI option, source discovery
checks `spec/spec.py`, `spec/spec.json`, and YAML files under `spec/` beneath
the project root:

- If only `spec/spec.py` exists, its `spec` variable is selected automatically.
- If only `spec/spec.json` exists, it is selected automatically.
- If only YAML files exist, their directory is selected automatically.
- If multiple source types exist, the build fails as ambiguous. Select one
  with `--python-spec`, `--json-spec`, or `--yaml-spec`.
- If no source exists, the build fails and reports the expected paths.

Set one of `application.python_spec`, `application.json_spec`, or
`application.yaml_spec` in `uptimely.toml` to choose a source by default.
A CLI source option overrides the configured source.

Use `--python-spec`, `--json-spec`, or `--yaml-spec` to select a source
explicitly, including one outside the standard paths. YAML supports a file or
a directory of fragments as described in [YAML authoring](yaml-authoring.md).
A Python spec is imported as a module, with
the project root and configured source directory available for local imports.
Third-party packages still need to be installed in the active environment.
Use `--src-path` when project modules are in a directory other than `src/`.

### Examples

```console
uptimely build example
uptimely build example --log-level debug
uptimely build example --features pump_health_score
```

In the data center cooling pump example, `pump_health_score` is illustrative,
not a validated operational health limit.
