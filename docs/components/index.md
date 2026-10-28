# About

Uptimely Core uses specifications to make analytics understandable and
executable without tying their meaning to a particular script, runtime, or
deployment environment. A specification gives people and tools a shared,
checkable contract: what the analytics mean, what work must be done, and how
that work interacts with runtime data.

The workflow has three related specifications:

## Spec

The Spec document describes the analytical system: its entities,
dimensions, datasets, features, reusable functions, and bindings between
inputs and outputs. Declaring these relationships explicitly makes feature
dependencies visible, allows tools to validate and document the system, and
gives the compiler enough information to determine what calculations are
required. The document describes the spec; it does not implement the
functions or connect to live data.

## Compiler

The compiler specification defines how a Spec document becomes a
portable plan for deployment and execution. It resolves declared feature
dependencies into action dependencies, selects required calculations, and
orders function calls so independent work can be identified
and prerequisites run first. Keeping this step separate from execution makes
the plan inspectable and reusable, and lets errors in the declared workflow be
found before it runs.

## Engine

The engine specification defines how an execution plan is carried out. An
engine connects plan inputs to runtime data and function implementations,
invokes the planned work, and reports results and failures. Separating runtime
bindings from the Spec document lets the same definition and plan run
with environment-specific resources, while keeping execution behavior clear
and testable.
