# Inspector

The inspector compares each function template in the validated Spec with its bound Python implementation.

It checks function arguments and annotations against the declarations. It runs during the build, before the Compiler creates the execution plan.

When authoring the spec with Python interface in the same repository with source code, the spec declarations and Python codebase are pretty much integrated. Inspector is still useful as a standalone concept for cases when the spec and source code are defined in isolation.
