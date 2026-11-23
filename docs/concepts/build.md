# Build

A build reads a Spec, validates it, inspects implementation bindings, and
compiles an execution plan. The resulting bundle contains files that Explorer,
the Engine, and external frameworks can consume.

## Build sequence

1. Load and structurally parse the Spec.
2. Run Spec semantic validation.
3. Inspect enabled function bindings and implementation signatures.
4. Compile the validated Spec and inspected metadata into an execution plan.
5. Package the implementation and prepare bundle and Explorer artifacts.

## Build manifest

Basic build information such as artifact paths.

## Python spec serialization to json

If spec was authored in Pyhthon, to declrations are converted to json for the build bundle.

When authored manually by json, simply copied to the bundle.

## Operator compilation to invocations

The build invokes the compiler after Spec validation and binding inspection.
The compiler converts operator declarations into physical invocations and does
not perform implementation inspection.

## Explorer data

The build process prepares explorer data artifact. It restructures data from spec and execution plan to be suitable for rendering.

Function docstrings are parsed to show code documentation automatically.
