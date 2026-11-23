# Compiler

Compiler is the bridge between logical definitions and physical execution.
It consumes a validated Spec and optional inspected signature metadata. It does
not import entrypoints or inspect implementation signatures.

Execution plans contain named invocation results.

## Operators to invocations

Each operator compute binding and merge binding produces one invocation.
Compilation deterministically maps these bindings to explicit function calls
with stable invocation IDs. Calls remain traceable to their source operators.
The Compiler does not execute analytical functions or fuse operator calls into
hidden work.

## Resolving binding variables

The plan encoder resolves Spec bindings and encodes runtime references for
function arguments and returns in the scheduled invocations.

## Execution graph

The Compiler resolves dependencies between invocations and assigns them to
topological stages. For the same Spec and feature selection, it produces the
same invocation IDs and stage order.

The seed operator of the profile is always the first invocation.

## Execution optimization

The Compiler does not optimize dataframe operations. A dataframe
implementation may optimize expressions during execution when it supports lazy
evaluation.
