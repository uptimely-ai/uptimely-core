# Compiler

The Compiler transforms a Spec into a portable execution plan. It validates
the declarations, resolves the work required for the selected features, and
orders that work for the Engine. It does not execute analytical functions.

The [project services](project.md) use the Compiler during a build. The
resulting bundle contains both the Spec and plan, which the Engine consumes
later.

## Key concepts

### Operators and invocations

Spec operators declare how functions use inputs and produce outputs. The
Compiler turns this declared work into plan invocations, each representing a
function call. An operator can result in more than one invocation, for example
when a compute function produces a fragment that needs a separate merge.
Operators describe intent in the Spec; invocations are the executable steps in
the plan.

### Dependencies and stages

Declared feature inputs determine which invocations depend on others. The
Compiler resolves those dependencies, selects prerequisites for requested
features, and groups invocations into ordered stages. Dependencies must run
before their consumers; invocations in the same stage have no declared
dependency between them.

### Bound arguments

The plan records function arguments resolved from Spec declarations, including
references to features and profiles. References to runtime data are left for
the Engine to resolve during execution.

### Validation

Before creating the plan, the Compiler checks the Spec and the feasibility of
the requested feature selection. It also checks function entrypoints and, when
enabled, whether their signatures match the declared argument and return
contracts. These checks catch declaration problems before execution, but do
not verify that function implementations calculate correct results.

## Learn more

See the [Spec reference](spec.md) for declaration semantics, the
[Execution plan](execution-plan.md) for the Compiler's portable output, and the
[Python Compiler API](../reference/python/compiler.md) for compilation details.
