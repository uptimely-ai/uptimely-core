# Projects

`uptimely.project` resolves project paths, loads project specifications, and
builds or reads validated active build bundles. `read_build_bundle` holds a
reader lock for the duration of its context; use `load_build_bundle` when a
lock is not needed after loading.

Builds validate Spec semantics once during compilation. Explorer rendering and
staged and published bundle loading reuse that validation. Artifact, structural,
and execution-plan checks still run.

Standalone `load_build_bundle` and `read_build_bundle` validate Spec semantics by
default. Pass `validate=False` only when the saved Spec has already been
validated and has not changed; all other bundle checks remain enabled.

Project path constants and `resolve_path` are defined in
`uptimely.project_paths` and also exported by `uptimely.project`.
The former `uptimely.project.paths` forwarding module is removed.

::: uptimely.project
    options:
      heading_level: 2
      show_root_heading: false
      members:
        - build_project
        - load_build_bundle
        - read_build_bundle
        - load_spec_source
        - resolve_path
