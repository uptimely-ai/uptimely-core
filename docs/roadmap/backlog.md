# Backlog

Planned backend work.

## Add id for datasets

Add explicit ID for datasets in Spec json document.

## Simplify compiled plan structure

Now contains the full spec definition. Consider having only stages, callables, execution groups, schedules etc execution related information while keeping spec.json separate.

## Add optimization to compiler

Add optimization method to compiler configuration.

## Add freshness to spec

Defines how often each mapping or feature is needed.

Compiler can use this information to define scheduling eg by interval multiples.
