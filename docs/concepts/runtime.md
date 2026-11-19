# Runtime

A runtime provides the environment and dependencies in which a worker runs.
It includes the language version, installed packages, native libraries,
and execution capabilities.

```text
Runtime
└── Worker process
    └── Uptimely Engine
```

## Runtime and application

The runtime is separate from the analytical definition. The Spec describes
what to calculate. The runtime supplies the software and resources needed to
run it.

## Isolation levels

| Runtime type | What it isolates | Typical use |
| --- | --- | --- |
| Python virtual environment | Python packages | Local development and lightweight execution |
| Docker container | Python environment, operating-system files, and processes | Reproducible development and production |
| Virtual machine | Operating system and host resources | Strong host isolation |
| Managed platform | Platform-specific environment and scaling | Snowflake, Databricks, and similar services |

Docker usually provides enough isolation for Python analytics while remaining
portable across local machines and production infrastructure.

## Current Python runtime

Uptimely currently runs in the active Python environment. That environment
must contain:

- A supported Python version
- Uptimely Core
- Dependencies imported by project functions
- The dataframe backend required by the execution plan
- Access to configured input and output locations

The Engine checks that the configured dataframe backend matches the saved plan.

## User-managed isolation

Users can run Uptimely in a virtual environment or container and manage the
environment with their own tooling.

For example:

```bash
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/uptimely run
```

The same command can run in a Docker container, virtual machine, or managed
job environment. Uptimely uses the active runtime and does not create or
replace it.
