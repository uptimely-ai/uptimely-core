# Project

The project API resolves conventional project paths and Spec sources without
loading build or runtime configuration.

## Spec sources

Use `SpecSourceResolver.resolve` to select a source, then `load_spec_source` to
load it.

::: uptimely.project.spec_source
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - PythonSpecSource
        - JsonSpecSource
        - SpecSourceResolver
        - load_spec_source

## Python imports

::: uptimely.project.python_imports
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - expose

::: uptimely.codebase.python.imports
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - PythonModuleImportManager
