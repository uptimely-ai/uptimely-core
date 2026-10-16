# Backlog

Planned backend work.

## Add id for datasets

Add explicit ID for datasets in Analytics json document.

## Simplify compiled plan structure

Now contains the full analytics definition. Consider having only stages, callables, execution groups, schedules etc execution related information while keeping analytics.json separate.

## Add optimization to compiler

Add optimization method to compiler configuration.

## Add freshness to analytics

Defines how often each mapping or feature is needed.

Compiler can use this information to define scheduling eg by interval multiples.
