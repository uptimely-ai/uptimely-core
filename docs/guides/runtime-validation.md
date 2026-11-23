# Validate execution

## Python runtime preflight

Before running any operator, the Engine checks the bundle's Python version
constraint and verifies that dependencies whose environment markers match are
installed at compatible versions. This check reports missing or incompatible
dependencies together with any Python version mismatch.

The Engine does not install dependencies or verify transitive dependencies,
extras, or direct URL provenance. Bundles without a runtime definition skip
this check. See [Build bundle runtime requirements](../artifacts/build.md#runtime-requirements)
for how the metadata is generated.

## Runtime validation

Analytical runtime validation is not currently supported. `uptimely run
--validate` and `Engine.run(validate=True)` fail before executing the plan.

The Engine checks configuration, plan structure, and runtime compatibility,
but does not check returned data against analytical contracts. Function and
dataframe errors can fail execution, and configured functions can have
external side effects. See [Engine execution](../concepts/engine.md#plan-execution)
for execution order and failure handling.

## Runtime validation and configuration

See [Configure a project](configuration.md#runtime-values) for runtime values,
paths, parameters, and backend settings.
