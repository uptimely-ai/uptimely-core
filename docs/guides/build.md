# Build a project

### Specification source discovery

Without a source setting in `uptimely.toml` or CLI option, source discovery
checks `spec/spec.py` and `spec/spec.json` beneath the project root:

- If only `spec/spec.py` exists, it is selected automatically.
- If only `spec/spec.json` exists, it is selected automatically.
- If both exist, the build fails as ambiguous. Select one with
  `--python-spec` or `--json-spec`.
- If neither exists, the build fails and reports the expected paths.

Set either `application.python_spec` or `application.json_spec` in `uptimely.toml` to
choose a source by default. They cannot both be set. A CLI source option
overrides both configured source settings.

Use `--python-spec` or `--json-spec` to select a source explicitly, including
one outside the standard paths. A Python spec is imported as a module, with
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
