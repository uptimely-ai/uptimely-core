# Release 1: Explorer navigation, focused lineage, and dependency views

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Explorer explanations

| title | breaking | description |
|---|---|---|
| Add explanations for non-experts | No | Extend metadata extraction with `Explanation:` and `Formula:` sections containing argument placeholders. Explorer fills them with bound feature descriptions and units and combines them into output lineage stories. |

## Work package: Explorer navigation and contextual controls

Separate resource lookup from dependency exploration without replacing the
traditional navigation shell. Keep Plan and Run mostly unchanged.

**Priority:** High.

**Prerequisites:** Existing Explorer catalogs, client-side navigation, and
static presentation snapshots.

| title | breaking | description |
|---|---|---|
| Separate Catalog and Lineage navigation | No | Rename Analytical model to Catalog for declaration browsing. Give Lineage its own section, initially containing the existing feature-lineage page, with Overview and Matrix added by later packages. Keep existing profile cards in Catalog rather than creating another equivalent card overview. Preserve resource direct links and browser history when reorganizing navigation. |
| Share resource details and exploration entry points | No | Reuse resource-detail content across Catalog and Lineage instead of maintaining competing descriptions. Link graph selections to their Catalog resources and add Explore dependencies entry points for profiles and features. Keep functions and dimensions directly searchable and browsable without graph navigation. |
| Separate view options from selection context | No | Use page-specific toolbars for search, scope, and display settings. Keep the active graph scope and fit/zoom controls visible on mobile. Put less frequent settings and legends under Options, separate from selected-resource actions and details. Replace the graph selection dialog on mobile with a compact, expandable bottom sheet with explicit close and expand controls. Do not stack Options and selection overlays. Preserve other pages' contextual navigation. |
| Verify navigation and mobile interaction | No | Test direct links, browser back/forward, keyboard navigation, selection details, overlay dismissal, narrow-screen layouts, and existing Plan and Run behavior. Page and focus changes belong in navigation history, while zoom, legend visibility, and transient graph selections do not create history entries. Update Explorer documentation for the new sections and contextual controls. |

## Work package: Focused feature lineage

Make feature search and bounded neighborhood exploration the base behavior,
with the full 2D/3D graph available as an explicit overview.

**Priority:** High.

**Prerequisites:** Explorer navigation and contextual controls.

| title | breaking | description |
|---|---|---|
| Define browser graph-query semantics | No | Keep Python build responsible for resolved, validated feature/operator dependencies, stable IDs, and metadata. Build incoming/outgoing adjacency indexes once in JavaScript and reuse them for interactive queries. Keep FastAPI serving snapshots without recompiling on interaction. Define root IDs, direction, feature-dependency depth, and node budget independently of operator visibility. Keep execution build scope distinct from Explorer view scope. Preserve static-export behavior without requiring a Python server. |
| Add focused neighborhoods and progressive expansion | No | Search for a feature and display its immediate inputs and consumers by default. Remove unrelated nodes from the layout rather than merely dimming them. Offer upstream/downstream expansion and explicit full ancestry or impact actions. Show boundary counts and distinguish hidden dependencies, budget-limited results, and genuinely absent connections. Apply operator visibility as a display projection without changing scope semantics. |
| Persist focus and validate scale | No | Persist focus, direction, and expansion scope in URLs and restore them through history. Test cross-profile traversal, shared producers, operator show/hide equivalence, isolated features, bounded results, and static exports. Measure snapshot size, memory, query latency, and visible-graph layout time on larger fixtures. Use a Web Worker if query work blocks interaction, but defer server queries or graph chunking until measurements justify them. Document the supported scope and any measured limits. |

## Work package: Profile lineage overview and drill-down

Add a dependency overview rather than duplicating the Catalog profile cards.
Use dedicated profile focus as the main drill-down mode, especially on mobile.

**Priority:** High.

**Prerequisites:** Focused feature lineage.

| title | breaking | description |
|---|---|---|
| Summarize direct profile dependencies | No | Add Lineage Overview with one collapsed node per profile and aggregated direct cross-profile feature dependencies. Retain the underlying feature relationships for inspection. Explain that profile aggregation can show apparent cycles even when feature lineage is acyclic and must not be interpreted as an execution DAG. |
| Add profile focus with external boundaries | No | Open a scoped profile view showing internal features/operators and compact external boundary nodes or ports. Identify relevant input and consumer features, provide boundary counts, and allow users to inspect or focus a neighboring profile. Offer feature-neighborhood focus from the same view, with breadcrumbs, direct links, and a clear return to the previous scope. Make Focus profile the primary mobile action. |
| Support bounded in-place expansion | No | Allow a few profiles to expand together in the overview, with named external ports and only connections relevant to their displayed contents. Keep expansion distinct from navigation to a focused profile. Preserve selection on collapse and avoid unnecessary layout movement. Apply explicit visibility budgets rather than recreating the full graph accidentally. |
| Verify overview and drill-down | No | Test aggregate-edge provenance, cross-profile connections, apparent profile cycles, expand/collapse, focus history, stable selection, mobile boundaries, and static exports. Update Explorer documentation to distinguish Catalog cards, dependency overview, in-place expansion, and focused drill-down. |

## Work package: Source-to-target lineage tracing

Improve existing lineage highlighting with an explicit, narrowly scoped
source-to-target exploration workflow rather than duplicating it.

**Priority:** High.

**Prerequisites:** Focused feature lineage.

| title | breaking | description |
|---|---|---|
| Add explicit source and target selection | No | Reuse existing graph selection and highlighting to choose a source and target. Display only nodes and edges on directed paths between them, preserving branches and producing operators. Distinguish the complete path corridor from any simplified representative path and report disconnected endpoints or budget-limited results explicitly. |
| Verify path scope and navigation | No | Test branching, shared intermediates, cross-profile paths, identical endpoints, disconnected selections, operator visibility, and bounded output. Persist endpoints in direct links and history, support mobile endpoint selection, and document how tracing differs from full ancestry and downstream impact. |

## Work package: Profile dependency matrix

Add a compact coupling view that opens the same focused lineage workflow.
Nested feature-level matrices are outside this initial package.

**Priority:** High.

**Prerequisites:** Profile lineage overview and drill-down.

| title | breaking | description |
|---|---|---|
| Add the profile dependency matrix | No | Add Lineage Matrix with supplying profiles as rows and consuming profiles as columns. Count distinct direct feature-to-feature dependency pairs across each profile boundary, collapsing operators and deduplicating repeated pairs. Label the count definition and treat within-profile dependencies separately. Provide search, deterministic ordering, and virtualization when needed rather than relying on color alone. |
| Connect matrix selections to focused lineage | No | Selecting a cell lists its exact source/target feature pairs and offers Explore these dependencies. Row and column actions show profile consumers and suppliers. Reuse profile focus and resource details, with mobile-friendly cell inspection and accessible non-visual dependency lists. |
| Distinguish direct dependencies from reachability | No | Offer a clearly labeled reachability mode separately from direct-pair counts. Derive reachability from actual feature paths rather than paths through the collapsed profile graph, which can imply connections that do not exist. |
| Verify matrix semantics and usability | No | Test direction labels, deduplication, cell provenance, empty cells, apparent profile cycles, reachability, ordering, focused-lineage links, keyboard access, mobile scrolling, and static exports. Document how the matrix answers coupling questions rather than execution order or run status. |
