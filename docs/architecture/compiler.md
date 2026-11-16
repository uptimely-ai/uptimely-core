# Compiler

The Compiler transforms a Spec into a portable execution plan. It validates
the declarations, resolves the work required for the selected features, and
orders that work for the Engine. It does not execute analytical functions.

The [App](application.md) uses the Compiler during a build. The
resulting bundle contains both the Spec and plan, which the Engine consumes
later.

## Learn more

See the [Spec reference](../reference/formats/spec/index.md) for declaration semantics, the
[Execution plan](../reference/formats/execution-plan.md) for the Compiler's portable output, and the
[Python Compiler API](../reference/python/compiler.md) for compilation details.
