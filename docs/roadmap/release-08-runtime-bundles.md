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

## Work package: Runtime manifests and function binding

Define isolated dependency stacks as runtimes, separate from development,
test, and production configuration environments.

**Prerequisites:** Existing Spec JSON, deferred function references, project
layout, and the source/import metadata from Release 7.

| title | breaking | description |
|---|---|---|
| Define portable runtime manifests | Yes | Add language-neutral `runtimes/<id>/runtime.json` definitions for worker commands, protocol versions, dependency inputs, and required capabilities. |
| Define language-specific dependency inputs | Yes | Let Python runtimes reference dependency files and a Python version. Allow other languages to use their own ecosystem inputs. |
| Keep deployment policy outside runtime manifests | Yes | Keep host placement, credentials, and orchestration policy out of runtime definitions. |
| Bind functions to runtimes | Yes | Carry optional function-runtime references through decorators, Python authoring, Spec JSON, and plans. |

## Work package: Runtime source layout and project configuration

Resolve each implementation's owning runtime before importing it and keep
project source configuration consistent across tools.

**Prerequisites:** Runtime manifests and function binding.

| title | breaking | description |
|---|---|---|
| Map source packages to runtime definitions | Yes | Use `src/<runtime-id>/` for implementations and `runtimes/<runtime-id>/` for definitions. Resolve the runtime before importing a function and validate any decorator declaration. |
| Associate external implementation packages | Yes | Require an explicit runtime association for implementation packages outside the project source mapping. |
| Configure the project source root and Spec entrypoint | Yes | Support optional root `uptimely.toml` settings for the source path and Python Spec entrypoint. Explicit CLI options take precedence, with existing conventions as fallback. |
| Reuse resolved project layout across tools | Yes | Use one resolved source root and Spec entrypoint for build, engine, Explorer, and MCP operations. Preserve existing CLI and Python API parameters. |
| Preserve package imports during isolation | Yes | Keep imports consistent when `src` is a package and include qualified names such as `src.*` in import-state isolation. Do not add upward discovery, environment overrides, a second config source, or a custom import finder. |
| Update project scaffolding and guidance | Yes | Update examples, entrypoints, and project-structure documentation. Keep incompatible runtime implementations in separate Python modules. |

## Work package: Runtime cache isolation

Separate machine-local runtime installations from portable build outputs.

**Prerequisites:** Runtime manifests and function binding.

| title | breaking | description |
|---|---|---|
| Separate runtime caches from generated outputs | No | Store machine-local installations under `.cache/uptimely/runtimes/<content-hash>/`, separate from `_generated/`. Ignore caches in version control and exclude them from bundles. |
| Define runtime cache identity and cleanup | No | Derive cache identity from runtime and provisioning inputs. Define invalidation and explicit cleanup. Keep Docker images in Docker-managed storage. |
| Validate runtime paths and references | No | Test missing definitions, conflicting runtime references, and portable path validation. |

## Work package: Locked Python runtime provisioning

Provision function dependencies without inheriting the developer's Poetry
environment.

**Prerequisites:** Runtime manifests and function binding, Runtime source
layout and project configuration.

| title | breaking | description |
|---|---|---|
| Define maintained Python dependency inputs | No | Support maintained dependency declarations and explicit lock generation with transitive pins, hashes where supported, Python version, and credential-free package indexes. |
| Provision locked Python environments | No | Use uv by default and provide a pip alternative for locked pip-compatible requirements. Respect destination platform constraints. |
| Make provisioning explicit | No | Provision only through a preparation command or deployment request. Report installation and compatibility failures. Never install dependencies implicitly during compilation. |

## Work package: Python worker installation and development

Run Python functions with a compatible worker and their isolated interpreter.

**Prerequisites:** Locked Python runtime provisioning.

| title | breaking | description |
|---|---|---|
| Install a compatible Uptimely worker | No | Install a pinned compatible worker in each Python runtime and check protocol and plan compatibility. Non-Python runtimes implement the protocol without installing the Python package. |
| Launch with the runtime interpreter | No | Launch directly with the selected interpreter, without developer-environment activation or inherited Python package paths. |
| Install project code in runtime environments | No | Define project implementation installation for development and later immutable bundles. |
| Verify isolated runtime development | No | Test missing packages, conflicting versions, stale caches, interpreter selection, and provisioning failures. |
| Document runtime-specific editing and testing | No | Use each runtime's interpreter for editing and tests where supported. Do not merge venv `site-packages` or rely on a development superset for correctness. |

## Work package: Runtime-isolated contract extraction

Load the Spec and compile portable contracts without importing analytical
implementations into the developer or compiler process.

**Prerequisites:** Python worker installation and development.

| title | breaking | description |
|---|---|---|
| Resolve deferred entrypoints in the owning runtime | Yes | Batch inspection requests by runtime and import implementations only inside their assigned runtime. |
| Return serializable implementation contracts | Yes | Return argument names, logical types, required-argument information, return roles, decorator metadata, descriptions, and package provenance. Do not return live callables or type objects. |
| Keep contract inspection non-executing | Yes | Do not call analytical functions during inspection. Report import failures clearly and document that module-level initialization still runs in the worker. |

## Work package: Compiler integration with runtime contracts

Use extracted contracts consistently across compilation and build-time tools.

**Prerequisites:** Runtime-isolated contract extraction.

| title | breaking | description |
|---|---|---|
| Replace compiler-local signature imports | Yes | Use runtime inspection results for compiler binding validation. Apply the same isolation to authoring conversion, documentation generation, and other inspection tools. |
| Cache contracts by source and runtime identity | Yes | Prevent stale contract reuse when source or runtime inputs change. |
| Support portable contracts without provisioning | Yes | Allow explicit contracts for non-Python implementations or builds without runtime provisioning. Check implementation compatibility before execution. |
| Verify build-time isolation | No | Use fixtures with incompatible dependencies absent from the compiler environment. Verify Spec loading, inspection, compilation, and documentation without importing those packages into the parent process. |
| Test inspection side effects and cache invalidation | No | Cover runtime discovery, worker-confined import side effects, annotation resolution, contract drift, and cache invalidation. |

## Work package: Portable execution bundle format

Extend immutable build snapshots into deployable artifacts containing code and
runtime requirements, not machine-local installations.

**Prerequisites:** Immutable build snapshots, Compiler integration with runtime
contracts.

| title | breaking | description |
|---|---|---|
| Define the versioned bundle manifest | No | Include build identity, compatibility metadata, and content hashes. Reuse immutable build identity rather than creating a second snapshot mechanism. |
| Package execution inputs | No | Include the saved Spec, plan, inspected contracts, implementation wheels or supported source archives, assets, runtime definitions, and dependency locks. |
| Define bundle inclusion and exclusion rules | No | Use explicit inclusion rules and reject unsafe archive paths. Exclude secrets, venvs, caches, data, and diagnostics unless a supported asset is selected. |

## Work package: Destination bundle preparation

Validate portable bundles and recreate their required runtime at the destination.

**Prerequisites:** Portable execution bundle format.

| title | breaking | description |
|---|---|---|
| Verify and safely extract destination bundles | No | Check integrity and protocol compatibility before safe extraction. |
| Prepare destination runtimes | No | Install implementations from the artifact and recreate runtime installations at the destination. |
| Support online and offline preparation explicitly | No | Distinguish dependency installation or image pulls from offline deployment with separately supplied compatible wheels or images. Requirements alone do not guarantee offline or cross-platform execution. |
| Test bundle integrity and portability | No | Test round trips, missing or modified artifacts, source changes after export, archive traversal, excluded cache/secret files, platform mismatches, and installation failures. |
| Document bundle contents and limits | No | Explain bundle contents, reproducibility limits, and the difference between dependency requirements and bundled dependencies. |
