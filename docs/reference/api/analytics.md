# Analytics

`uptimely.analytics` separates the analytics document from loading, preparation,
and serialization. `Analytics` contains document fields; derived functions and
calls belong to `PreparedAnalytics`.

The [analytics format reference](../../components/analytics.md) describes the
contract. See [Python authoring](python.md) for declarations that produce it, or
[feature graphs](feature-graph.md) for dependency analysis.

<div class="api-reference" markdown="1">

## Package map

| Module or subpackage | Purpose |
| --- | --- |
| [api](analytics/api.md) | Load, convert, and prepare analytics with semantic validation. |
| [model](analytics/model.md) | Define the analytics document, datasets, bindings, and function metadata. |
| [resolved](analytics/resolved.md) | Inspect prepared analytics, resolved functions, and calls. |
| [json](analytics/json.md) | Write analytics documents as JSON. |
| [validation](analytics/validation.md) | Check document relationships and inspect structured validation errors. |
| [python](python.md) | Author analytics using Python declarations. |
| [feature_graph](feature-graph.md) | Inspect feature dependencies and select subgraphs. |

## Working with analytics

1. Load a JSON document or convert Python declarations using
   [api](analytics/api.md).
2. Work with the document types defined in [model](analytics/model.md).
3. Prepare the document to obtain [resolved](analytics/resolved.md) functions
   and calls for compilation or inspection.
4. Write the analytics document using [json](analytics/json.md).

Public convenience imports such as `uptimely.analytics.Analytics` and
`uptimely.analytics.load_analytics` remain available. The reference pages
document each interface in its defining module.

</div>
