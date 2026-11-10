# Projects

`uptimely.project` resolves project paths, loads project specifications, and
builds or reads validated active build bundles. `read_build_bundle` holds a
reader lock for the duration of its context; use `load_build_bundle` when a
lock is not needed after loading.
Call `build()` to build the current directory, or pass a project root explicitly.

Builds validate Spec semantics once during compilation. Explorer rendering and
staged and published bundle loading reuse that validation. Artifact, structural,
and execution-plan checks still run.
The source Spec remains authoritative for function contracts, binding roles,
and optional categories. Rebuild after changing declarations to regenerate the
portable plan and Explorer presentation snapshot.

Standalone `load_build_bundle` and `read_build_bundle` validate Spec semantics by
default. Pass `validate=False` only when the saved Spec has already been
validated and has not changed; all other bundle checks remain enabled.

Project path constants and `resolve_path` are defined in
`uptimely.project.paths` and exported by `uptimely.project`. Import them from
`uptimely.project.paths`; the former `uptimely.project_paths` forwarding module
has been removed.

Portable execution-plan models and serialization live in `uptimely.plan`. The
former `uptimely.execution_plan` forwarding package has been removed; update
imports to `uptimely.plan`.

::: uptimely.project
    options:
      heading_level: 2
      show_root_heading: false
      members:
        - build
        - load_build_bundle
        - read_build_bundle
        - load_spec_source
        - resolve_path
