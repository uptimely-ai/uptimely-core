# Feature graphs

`FeatureGraph` shows how features depend on one another in a Spec. Use
`FeatureSubGraph` to inspect a selected part of the graph. The Explorer
visualizes these relationships.

Creating a graph validates the Spec by default. Use `validate=False` only if
the Spec has already been validated and has not changed.

::: uptimely.spec.feature_graph.feature_graph
    options:
      heading_level: 2
      show_root_heading: false
      members: [FeatureGraphBase, FeatureGraph, FeatureSubGraph, FeatureGraphNodeMeta]

::: uptimely.spec.feature_graph.models
    options:
      heading_level: 2
      show_root_heading: false
      members: [FeatureNode, OperatorNode]
