# Project

The project API resolves conventional project paths and Spec sources without
loading build or runtime configuration.

## Spec sources

::: uptimely.project.spec_source
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - PythonSpecSource
        - JsonSpecSource
        - SpecSourceResolver
        - load_spec_source
        - load_project_spec

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
