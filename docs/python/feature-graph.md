# Feature graphs

`uptimely.spec.feature_graph` represents dependencies between features and
actions and supports subgraph selection. The Explorer visualizes those
relationships in **Lineage**, distinct from **Topology** (invocation dependencies)
and **Animation** (the execution walkthrough).

<div class="api-reference" markdown="1">

## feature_graph

`uptimely.spec.feature_graph.feature_graph` exposes the complete feature
dependency graph and feature subgraphs.

::: uptimely.spec.feature_graph.feature_graph
    options:
      heading_level: 3
      show_root_heading: false
      members: [FeatureGraphBase, FeatureGraph, FeatureSubGraph, FeatureGraphNodeMeta]

`Node` is the graph library's node type, re-exported from
`uptimely.spec.feature_graph`. `FeatureGraphNodeMeta` describes the feature or action metadata carried by a node.

## models

`uptimely.spec.feature_graph.models` defines the metadata attached to
feature and action nodes.

::: uptimely.spec.feature_graph.models
    options:
      heading_level: 3
      show_root_heading: false
      members: [FeatureNode, ActionNode]

</div>
