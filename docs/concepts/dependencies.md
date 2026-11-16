# Dependencies and execution

## Key concepts

### Operators and invocations

Operators declare work, while invocations represent function calls. Each
operator creates a compute invocation and, when declared, a separate merge
invocation.

### Dependencies and stages

Declared feature inputs determine which invocations depend on others. The
Compiler resolves those dependencies, selects prerequisites for requested
features, and groups invocations into ordered stages. Dependencies must run
before their consumers; invocations in the same stage have no declared
dependency between them.

Seed and dataset prerequisites also determine order. Fragment consumers wait
for the merge. Python assembly groups do not control scheduling.

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
