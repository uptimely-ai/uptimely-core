# Release 1: Explorer navigation, focused lineage, and dependency views

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Work package: Explorer explanations

| title | breaking | description |
|---|---|---|
| Extract explanation and formula sections | No | Recognize `Explanation:` and `Formula:` metadata sections with argument placeholders. |
| Render bound lineage explanations | No | Fill placeholders with bound feature descriptions and units, then combine the text into output lineage stories. |

## Work package: Explorer navigation and contextual controls

Separate resource lookup from dependency exploration without replacing the
traditional navigation shell. Keep Plan and Run mostly unchanged.

**Priority:** High.

**Prerequisites:** Existing Explorer catalogs, client-side navigation, and
static presentation snapshots.

| title | breaking | description |
|---|---|---|
| Separate Catalog and Lineage sections | No | Rename Analytical model to Catalog and move feature lineage into a separate Lineage section. Keep existing profile cards in Catalog. |
| Preserve resource navigation history | No | Preserve direct resource links and browser history while reorganizing navigation. Page and focus changes create history entries, while zoom, legend visibility, and transient selections do not. |
| Reuse resource details across sections | No | Share resource-detail content across Catalog and Lineage, and link graph selections to their Catalog resources. |
| Add dependency exploration entry points | No | Add Explore dependencies actions for profiles and features. Keep functions and dimensions searchable and browsable without graph navigation. |
| Add page-specific view toolbars | No | Separate search, scope, and display settings from selected-resource actions and details. Keep graph scope and fit/zoom controls visible on mobile. |
| Improve graph options and mobile selection | No | Put less frequent settings and legends under Options. Replace the mobile selection dialog with an expandable bottom sheet and prevent stacked overlays. |
| Verify navigation and update documentation | No | Test direct links, browser history, keyboard navigation, selection details, overlays, narrow layouts, and existing Plan and Run behavior. Document the new sections and controls. |

## Work package: Browser graph query foundations

Provide reusable, bounded dependency queries from the existing build snapshot.

**Priority:** High.

**Prerequisites:** Explorer navigation and contextual controls.

| title | breaking | description |
|---|---|---|
| Build reusable browser adjacency indexes | No | Keep Python responsible for resolved, validated dependencies, stable IDs, and metadata. Build incoming and outgoing indexes once in JavaScript and reuse them for queries. |
| Define bounded graph-query parameters | No | Define root IDs, direction, feature-dependency depth, and node budget independently of operator visibility. Keep execution build scope separate from Explorer view scope. |
| Preserve static graph snapshots | No | Serve snapshots through FastAPI without recompiling on interaction and preserve behavior in static exports without a Python server. |

## Work package: Focused feature neighborhoods

Make feature search and bounded neighborhood exploration the base behavior,
with the full 2D/3D graph available as an explicit overview.

**Priority:** High.

**Prerequisites:** Browser graph query foundations.

| title | breaking | description |
|---|---|---|
| Add focused feature neighborhoods | No | Search for a feature and show its immediate inputs and consumers. Remove unrelated nodes from the layout rather than dimming them. |
| Expand neighborhoods and report boundaries | No | Add upstream/downstream expansion and explicit ancestry or impact actions. Show boundary counts and distinguish hidden, budget-limited, and absent connections. |
| Keep operator visibility as a display projection | No | Apply operator visibility without changing query scope semantics. |

## Work package: Persistent and scalable graph focus

Make focused graph views shareable and verify their performance on larger
snapshots.

**Priority:** High.

**Prerequisites:** Focused feature neighborhoods.

| title | breaking | description |
|---|---|---|
| Persist graph focus in URLs | No | Persist focus, direction, and expansion scope in URLs and restore them through browser history. |
| Measure graph query and layout scale | No | Test cross-profile paths, shared producers, isolated features, bounded results, operator visibility, and static exports. Measure snapshot size, memory, query latency, and layout time on larger fixtures. Use a Web Worker only if measurements show interaction blocking. |
| Document supported graph limits | No | Document supported query scope and measured limits. Defer server queries and graph chunking until measurements justify them. |

## Work package: Profile lineage overview and focus

Add a dependency overview rather than duplicating the Catalog profile cards.
Use dedicated profile focus as the main drill-down mode, especially on mobile.

**Priority:** High.

**Prerequisites:** Focused feature neighborhoods.

| title | breaking | description |
|---|---|---|
| Summarize direct profile dependencies | No | Add one collapsed node per profile and aggregate direct cross-profile feature dependencies. Retain the underlying feature relationships for inspection. |
| Explain profile aggregation semantics | No | Explain that aggregation may show apparent profile cycles even when feature lineage is acyclic. Do not present the overview as an execution DAG. |
| Add focused profile boundaries | No | Show a profile's internal features and operators with compact external boundary nodes, relevant input/consumer features, and boundary counts. |
| Navigate between profile and feature focus | No | Allow users to inspect or focus neighboring profiles and feature neighborhoods. Provide breadcrumbs, direct links, and a clear return to the previous scope. |
| Make profile focus mobile-friendly | No | Make Focus profile the primary mobile action and keep boundary inspection usable on narrow screens. |

## Work package: Bounded profile expansion

Expand a small number of profile nodes in place without replacing focused
profile navigation.

**Priority:** High.

**Prerequisites:** Profile lineage overview and focus.

| title | breaking | description |
|---|---|---|
| Expand profiles within the overview | No | Allow a bounded number of profiles to expand together, showing named external ports and only relevant connections. Keep expansion distinct from focused-profile navigation. |
| Preserve selection and layout on collapse | No | Preserve selection on collapse, avoid unnecessary layout movement, and apply explicit visibility budgets. |
| Verify overview and drill-down behavior | No | Test edge provenance, cross-profile connections, apparent cycles, expand/collapse, focus history, selection, and mobile boundaries. |
| Document profile lineage views | No | Verify static exports and distinguish Catalog cards, dependency overview, in-place expansion, and focused drill-down in Explorer docs. |

## Work package: Source-to-target lineage tracing

Improve existing lineage highlighting with an explicit, narrowly scoped
source-to-target exploration workflow rather than duplicating it.

**Priority:** High.

**Prerequisites:** Focused feature neighborhoods.

| title | breaking | description |
|---|---|---|
| Select source and target resources | No | Reuse graph selection and highlighting to choose source and target features. |
| Display the directed path corridor | No | Show only nodes and edges on directed paths between endpoints, preserving branches and producing operators. Distinguish the full corridor from a simplified representative path. |
| Report tracing limits | No | Report disconnected endpoints and budget-limited results explicitly. |
| Persist and verify trace navigation | No | Persist endpoints in direct links and history. Test branching, shared intermediates, cross-profile paths, identical endpoints, operator visibility, and bounded results. |
| Document source-to-target tracing | No | Support mobile endpoint selection and explain how tracing differs from full ancestry and downstream impact. |

## Work package: Profile dependency matrix

Add a compact coupling view that opens the same focused lineage workflow.
Nested feature-level matrices are outside this initial package.

**Priority:** High.

**Prerequisites:** Profile lineage overview and focus.

| title | breaking | description |
|---|---|---|
| Define direct profile-pair counts | No | Count distinct direct feature-to-feature pairs across profile boundaries, collapsing operators and deduplicating repeated pairs. Treat within-profile dependencies separately. |
| Add the profile dependency matrix | No | Show supplying profiles as rows and consuming profiles as columns. Label the count definition, support search and deterministic ordering, and virtualize large matrices. Do not rely on color alone. |
| Connect matrix cells to feature pairs | No | Selecting a cell lists its exact source/target feature pairs and offers Explore these dependencies. |
| Add profile row and column actions | No | Show profile consumers and suppliers and reuse profile focus and resource details. |
| Distinguish direct dependencies from reachability | No | Offer a clearly labeled reachability mode separately from direct-pair counts. Derive reachability from actual feature paths rather than paths through the collapsed profile graph, which can imply connections that do not exist. |

## Work package: Profile matrix accessibility and verification

Validate dependency-matrix semantics and make cell inspection accessible.

**Priority:** High.

**Prerequisites:** Profile dependency matrix.

| title | breaking | description |
|---|---|---|
| Make matrix inspection accessible | No | Support mobile cell inspection and accessible non-visual dependency lists. |
| Verify matrix dependency semantics | No | Test direction labels, deduplication, cell provenance, empty cells, apparent cycles, reachability, ordering, and focused-lineage links. |
| Verify matrix accessibility and exports | No | Test keyboard access, mobile scrolling, and static exports. |
| Document matrix interpretation | No | Explain how the matrix answers coupling questions rather than execution order or run status. |
