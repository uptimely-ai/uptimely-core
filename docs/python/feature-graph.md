# Feature graphs

`uptimely.spec.feature_graph` provides dependency analysis and subgraph
selection. Graph rendering belongs to
[uptimely.explorer.graph_render](explorer.md#graph_render), not this package.

<div class="api-reference" markdown="1">

## graph

`uptimely.spec.feature_graph.graph` exposes the complete feature graph and
feature-level subgraphs.

::: uptimely.spec.feature_graph.graph
    options:
      heading_level: 3
      show_root_heading: false
      members: [GraphBase, FeatureGraph, SubGraph, NodeMeta]

`Node` is the graph library's node type, re-exported from
`uptimely.spec.feature_graph`. `NodeMeta` describes the feature or function
metadata carried by a node.

## models

`uptimely.spec.feature_graph.models` defines the metadata attached to
feature and function nodes.

::: uptimely.spec.feature_graph.models
    options:
      heading_level: 3
      show_root_heading: false
      members: [FeatureNode, FunctionNode]

</div>
