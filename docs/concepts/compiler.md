# Compiler

Compiler is the bridge between logical definitions and physical execution.

## Operators to invocations

Compiler converts logical operators to physical function invocations. Binding
connects each operator to a function and its associated arguments.

## Resolving binding variables

The compiler resolves object references to the actual values used in function
calls. It validates those values and binds them to the corresponding
invocations.

## Execution graph

Currently compiler's most important job is to creates an ordered graph of invocations based on features dependencies of the operators. In the current implementation each compute and merge action becomes one invocation.

The seed operator of the profile is always the first invocation.

The graph can be split to topological stages, where each invocation could be executed in parallel.

## Execution optimization

In the future, it is possible that compiler would apply more advanced optimization stragies to convert logical recipe to most performant execution plan.
