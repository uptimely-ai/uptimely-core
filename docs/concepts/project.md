# Project {#project}

The project layer represents the filesystem structure of one Uptimely analytics
project. It owns standard paths, project defaults, and preparation of
project-local Python source.

Build, execution, and Explorer components can use these conventions without
depending on the configured [application layer](application.md). The
application layer composes those components and remains the convenient
high-level entry point.
