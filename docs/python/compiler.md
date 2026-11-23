# Compiler

`InvocationNode` carries an invocation's semantics and is identified by its
`node_id`. Its `create_id` method derives the ID from the function, profile,
operator, and binding role. Node equality and hashing use only the ID.
`InvocationGraph` orders nodes using the supplied dependency IDs.
`InvocationSemanticsBuilder.build` derives contracts for one operator.
`Compiler` creates operator invocations, indexes their publishers, and resolves
their dependencies before selecting and scheduling the graph. Its
`invocation_graph` method returns the complete graph or a feature-selected graph.

::: uptimely.compiler.compiler
    options:
      heading_level: 2
      show_root_heading: false
      members: [Compiler]
