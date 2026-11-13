# Release 8: Isolated runtime provisioning, contract inspection, and ZIP bundles

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Isolated runtime execution plan

The following work packages implement one design in stages. This is a proposed
layout and behavior, not a description of currently supported execution.

### Example project structure

```text
project/
├── pyproject.toml                     # Developer tooling dependencies
├── poetry.lock
├── runtimes/                          # Committed and bundled definitions
│   ├── cpu/
│   │   ├── runtime.json
│   │   ├── requirements.in            # Maintained Python dependencies
│   │   └── requirements.lock          # Locked installation input
│   └── pytorch_gpu/
│       ├── runtime.json
│       ├── requirements.in
│       ├── requirements.lock
│       └── Dockerfile                 # Alternatively a pinned image reference
├── src/                               # Importable implementation modules
│   ├── cpu/
│   │   └── analytics.py
│   └── pytorch_gpu/
│       └── predict.py
├── spec/
│   └── spec.py                        # Deferred implementation references
├── config/
│   └── config.json                    # Runtime parameters and engine controls
├── deployment/                        # User-owned bundle submission functions
│   ├── local.py
│   └── prefect.py
├── data/
│   ├── input/
│   └── output/
├── .cache/                            # Ignored machine-local reusable state
│   └── uptimely/
│       └── runtimes/
│           └── <content-hash>/
│               └── venv/
└── _generated/                        # Generated artifacts, not installations
    ├── build/
    ├── bundles/
    │   └── <build-id>.zip
    └── run/
```

Python packaging must keep the function modules importable, adding package
markers or a packaged source layout as needed. The CPU/GPU split is illustrative,
not a requirement that every project use these runtime names or Docker.
Requirements files are Python-specific inputs, not fields imposed on other
languages by the runtime contract.

### Prerequisites and constraints

- Existing Spec JSON and deferred entrypoints provide the declaration starting
  point. Runtime declarations and explicit provisioning precede isolated
  inspection, which precedes portable bundle export and whole-graph launchers.
  Each work package below names its actual prerequisites.
- The developer's Poetry environment supplies authoring, compiler, driver, and
  deployment tooling only. Every Python worker runtime includes pinned Uptimely
  Core and its own dependencies. Non-Python workers implement the compatible
  protocol rather than installing the Python package.
- Use `runtime` for dependency stacks and worker requirements. Keep development,
  test, and production configuration environments separate. Runtime definitions
  declare capabilities, while deployment selects hosts, resources, and secrets.
- Provision through an explicit preparation or deployment action. Inspection
  needs an already prepared runtime unless portable contracts are supplied
  explicitly. Neither Spec loading nor compilation silently installs packages.
- Definitions and locks are portable inputs. Venvs are machine-local caches and
  never bundled. Cache deletion requires reprovisioning, not an analytical
  change. Docker images live in Docker storage. Offline use requires compatible
  dependencies or images supplied in addition to requirements.
- Select each function runtime's interpreter for editing and testing, using
  folder/project mappings when useful. Do not merge venv package paths. The
  editor does not select interpreters from Uptimely decorators automatically.
- Arrow IPC carries representable tabular values, not lazy execution plans or
  arbitrary Python objects. Control metadata and non-tabular artifact references
  use a separate portable protocol. Unsupported boundaries fail explicitly.

### Expected behavior and delivery phases

1. Author the Spec using deferred function references. Resolve the owning runtime
   from `src/<runtime-id>/` before importing implementations, then check
   any `runtime="..."` decorator declaration for agreement. External packages
   need explicit runtime associations.
2. Inspect signatures, annotations, decorators, and documentation inside the
   owning runtime. Return portable contracts to the compiler. Inspection does
   not call analytical functions, but module-level code still runs in the
   worker. Apply this isolation to all implementation-inspection tools.
3. Compile and export immutable ZIP bundles with source, assets, Spec, plan,
   contracts, runtime definitions, dependency locks, and integrity metadata.
   Execution uses bundled implementations rather than mutable project files.
4. Initially deploy the entire graph as one isolated venv or Docker job.
   Reject graphs requiring multiple runtimes until segmented execution ships.
   User functions in `deployment/` submit bundles locally, through Prefect, or
   through other orchestrators without reproducing compiler scheduling.
5. Add compiler-selected segments, cutting flows at runtime changes or
   incompatible dataframe representations. Retain compatible native paths,
   materialize explicitly at Arrow IPC boundaries, and preserve merge,
   publication, and side-effect dependencies. Stages describe dependency
   levels, segments describe worker jobs, and partitions describe record
   subsets. These concepts are not interchangeable.
6. Evolve the engine from a whole-graph worker into a driver, first executing
   segments sequentially, then concurrently and across nodes. Publish only
   successful outputs and report failures and skipped dependents. Concurrency
   requires isolated state and bounded resources. Record partitioning and
   distributed-native dataframe execution remain separate capabilities.

## Work package: Function runtime declarations and project layout

Define isolated dependency stacks as runtimes, separate from development,
test, and production configuration environments.

**Prerequisites:** Existing Spec JSON, deferred function references, and
project layout.

| title | breaking | description |
|---|---|---|
| Define portable runtime declarations | Yes | Add language-neutral `runtimes/<id>/runtime.json` definitions with worker commands, protocol versions, dependency/build inputs, and required capabilities such as GPU support. Python targets reference dependency files and a Python version, while other languages can use their own ecosystem inputs. Keep host placement, credentials, and orchestration policy outside these definitions. Carry function runtime references through decorators, Python authoring, Spec JSON, and plans without making decorators mandatory. |
| Organize functions by runtime | Yes | Use `src/<runtime-id>/` for implementations and `runtimes/<runtime-id>/` for their definitions. Discover the runtime from this mapping before importing a function, then validate any decorator runtime declaration against it. Require explicit associations for external implementation packages. Update project scaffolding, examples, entrypoints, and project structure documentation together. Avoid mixing incompatible runtime implementations in one Python module. |
| Separate runtime caches from generated outputs | No | Store reusable machine-local installations under project-root `.cache/uptimely/runtimes/<content-hash>/`, separate from `_generated/` build and run outputs. Ignore caches in version control and exclude them from bundles. Define cache identity from runtime and provisioning inputs, invalidation, and explicit cleanup. Docker images remain in Docker-managed storage. Test missing definitions, conflicting runtime references, and portable path validation. |

## Work package: Isolated Python runtime provisioning

Provision function dependencies without inheriting the developer's Poetry
environment.

**Prerequisites:** Function runtime declarations and project layout.

| title | breaking | description |
|---|---|---|
| Provision locked Python runtimes | No | Use uv as the default venv provisioner with a pip alternative consuming locked pip-compatible requirements. Support maintained dependency declarations and explicit lock generation, including transitive pins, hashes where supported, Python version, package indexes without credentials, and destination platform constraints. Provision only through an explicit preparation command or deployment request, not implicit compiler dependency installation. Report installation and compatibility failures explicitly. |
| Include the Uptimely worker in each runtime | No | Install a pinned compatible Uptimely Core worker dependency in every Python runtime, with explicit protocol and plan compatibility checks. Launch the runtime interpreter directly without developer-environment activation or inherited Python package search paths. Define how project implementation code is installed for development and later from immutable bundles. Do not require the Python package in non-Python runtimes, which must implement the compatible worker protocol. |
| Verify isolated development and installation | No | Test missing packages, conflicting dependency versions, stale caches, interpreter selection, and provisioning failures. Document editing functions with their runtime interpreter, using per-folder/project editor mappings where supported, and testing inside the actual runtime. Do not merge multiple venv `site-packages` or rely on a development superset for correctness. |

## Work package: Runtime-isolated function contract inspection

Load the Spec and compile portable contracts without importing analytical
implementations into the developer or compiler process.

**Prerequisites:** Isolated Python runtime provisioning.

| title | breaking | description |
|---|---|---|
| Extract contracts inside the owning runtime | Yes | Use deferred entrypoint references during Spec authoring. Batch inspection requests per runtime, import implementations inside that runtime, and return serializable argument names, logical types, required-argument information, return roles, decorator metadata, descriptions, and package provenance. Do not execute analytical functions during inspection or return live Python callables and type objects. Make import failures actionable and document that module-level initialization still runs. |
| Reuse extracted contracts across build tools | Yes | Replace compiler-local signature imports with runtime inspection results. Apply the same isolation to authoring conversion, documentation generation, and other implementation-inspection surfaces. Validate bindings against extracted contracts and cache results with source and runtime identity so changes cannot reuse stale metadata. Allow explicit portable contracts for non-Python implementations or compilation without runtime provisioning, with implementation compatibility checked before execution. |
| Verify build-time isolation | No | Add fixtures whose implementations require incompatible packages absent from the compiler environment. Verify Spec loading, inspection, compilation, and documentation without importing those packages into the parent process. Cover runtime discovery before decorator inspection, import side effects confined to workers, annotation resolution, explicit-contract drift, and cache invalidation. |

## Work package: Portable ZIP execution bundles

Extend immutable build snapshots into deployable artifacts containing code and
runtime requirements, not machine-local installations.

**Prerequisites:** Reproducible builds and diagnostics;
Runtime-isolated function contract inspection.

| title | breaking | description |
|---|---|---|
| Export versioned execution bundles | No | Package the saved Spec, execution plan, inspected contracts, implementation wheels or supported source archives, supporting assets, runtime definitions, dependency locks, and compatibility metadata in a ZIP with a versioned manifest and content hashes. Reuse immutable build identity and source packaging rather than creating a second snapshot mechanism. Use explicit inclusion rules and reject unsafe archive paths. Exclude secrets, venvs, caches, data, and diagnostics unless a supported asset is explicitly selected. |
| Define destination preparation and loading | No | Verify bundle integrity and protocol compatibility, extract safely, install implementations from the immutable artifact, and recreate runtime installations at the destination. Distinguish a source bundle requiring dependency installation or image pulls from offline deployment with separately supplied compatible wheels or images. Requirements alone do not guarantee offline execution or cross-platform compatibility. |
| Verify portable bundle execution inputs | No | Test round trips, missing and modified artifacts, source changes after export, archive traversal, excluded cache/secret files, destination platform mismatches, and explicit installation failures. Document bundle contents, reproducibility limits, and the difference between dependency requirements and bundled dependencies. |
