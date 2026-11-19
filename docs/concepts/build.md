# Build

A build is an operation that reads specification, runs compilation, infers semantical information and produces a build bundle. The bundle is set of files that can be consumed by Explorer and Engine but also other frameworks outside of Uptimely Core.

## Build manifest

Basic build information such as artifact paths.

## Python spec serialization to json

If spec was authored in Pyhthon, to declrations are converted to json for the build bundle.

When authored manually by json, simply copied to the bundle.

## Operator compilation to invocations

Build triggers compiler to convert spec declarations to physical execution plan.

## Explorer data

The build process prepares explorer data artifact. It restructures data from spec and execution plan to be suitable for rendering.

Function docstrings are parsed to show code documentation automatically.
