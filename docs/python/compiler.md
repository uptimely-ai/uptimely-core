# Compiler

`InvocationNode` represents an invocation by its `node_id`. Its `create_id`
method derives the ID from the function, profile, operator, and binding role.
These identity values are stored in the invocation semantics.
`InvocationGraph` orders nodes using the supplied dependency IDs.
`InvocationSemanticsBuilder.build` derives contracts for one operator.
`Compiler` creates operator invocations, indexes their publishers, and resolves
their dependencies before selecting and scheduling the graph.

::: uptimely.compiler.compiler
    options:
      heading_level: 2
      show_root_heading: false
      members: [Compiler]
