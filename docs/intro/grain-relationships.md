# Grain relationships

Operators' compute bindings can be inspected to infer semantical source-to-target relationships between source and target profile grains.


| Relationship | Source compared with target |
| --- | --- |
| `same` | Both have the same resolutions. |
| `expand` | The target refines the source by adding dimensions or selecting finer resolutions. |
| `collapse` | The target is coarser by removing dimensions or selecting coarser resolutions. |
| `emerge` | No source profile exists; the operator introduces data at the target grain. |
| `vanish` | No target profile exists; the operator consumes the source grain without producing a profile. |
| `fuse` | Multiple sources become one target.
| `unrelated` | Neither grain refines the other through the declared hierarchy. |
| `not_applicable` | A declared source cannot be resolved, or a profile grain is invalid. |

The comparison uses resolution hierarchy, not dimension counts. Sources include
logical feature owners and dataframe profiles. These labels do not perform
calculations or select a merge.

## Grain relationship visualization

The following examples compare source and target profile grain relationships. They show how the
observation keys relate, not how a function computes or transforms feature
values.

### Same grain

Both profiles select the same dimensions and resolutions. Their feature sets
and row scopes can still differ.

<div class="concepts-visual">
  <div class="cv-operation" role="group" aria-label="Same-grain relationship">
    <div class="cv-transform">
      <div>
        <span class="cv-tag">SOURCE PROFILE / one row per pump and timestamp</span>
        <div class="cv-table-scroll">
          <table class="cv-table">
            <thead><tr><th class="cv-key">cooling pump</th><th class="cv-key">timestamp</th></tr></thead>
            <tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td></tr></tbody>
          </table>
        </div>
      </div>
      <div class="cv-arrow"><span>same grain</span><b aria-hidden="true">&#8594;</b></div>
      <div>
        <span class="cv-tag">TARGET PROFILE / one row per pump and timestamp</span>
        <div class="cv-table-scroll">
          <table class="cv-table">
            <thead><tr><th class="cv-key">cooling pump</th><th class="cv-key">timestamp</th></tr></thead>
            <tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>

Profiles can also share a grain while covering different row scopes:

<div class="concepts-visual">
  <div class="cv-operation" role="group" aria-label="Same-grain profiles with different row scopes">
    <div class="cv-transform">
      <div>
        <span class="cv-tag">SOURCE PROFILE / wider row scope</span>
        <div class="cv-table-scroll">
          <table class="cv-table">
            <thead><tr><th class="cv-key">cooling pump</th><th class="cv-key">timestamp</th></tr></thead>
            <tbody><tr><td class="cv-key">P-01</td><td class="cv-key">08:59</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td></tr></tbody>
          </table>
        </div>
      </div>
      <div class="cv-arrow"><span>same grain</span><b aria-hidden="true">&#8594;</b></div>
      <div>
        <span class="cv-tag">TARGET PROFILE / narrower row scope</span>
        <div class="cv-table-scroll">
          <table class="cv-table">
            <thead><tr><th class="cv-key">cooling pump</th><th class="cv-key">timestamp</th></tr></thead>
            <tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>

### Expand

The target refines the source by adding a dimension or selecting a finer
resolution. This example adds the timestamp dimension.

<div class="concepts-visual">
  <div class="cv-operation" role="group" aria-label="Expanded grain relationship">
    <div class="cv-transform">
      <div>
        <span class="cv-tag">SOURCE PROFILE / one row per pump</span>
        <div class="cv-table-scroll">
          <table class="cv-table">
            <thead><tr><th class="cv-key">cooling pump</th></tr></thead>
            <tbody><tr><td class="cv-key">P-01</td></tr></tbody>
          </table>
        </div>
      </div>
      <div class="cv-arrow"><span>target refines source</span><b aria-hidden="true">&#8594;</b></div>
      <div>
        <span class="cv-tag">TARGET PROFILE / one row per pump and timestamp</span>
        <div class="cv-table-scroll">
          <table class="cv-table">
            <thead><tr><th class="cv-key">cooling pump</th><th class="cv-key">timestamp</th></tr></thead>
            <tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>

### Collapse

The target is coarser by removing a dimension or selecting a coarser resolution.
This example removes the timestamp dimension. The relationship does not specify
how target feature values are calculated.

<div class="concepts-visual">
  <div class="cv-operation" role="group" aria-label="Collapsed grain relationship">
    <div class="cv-transform">
      <div>
        <span class="cv-tag">SOURCE PROFILE / one row per pump and timestamp</span>
        <div class="cv-table-scroll">
          <table class="cv-table">
            <thead><tr><th class="cv-key">cooling pump</th><th class="cv-key">timestamp</th></tr></thead>
            <tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td></tr></tbody>
          </table>
        </div>
      </div>

      <div class="cv-arrow"><span>target is coarser</span><b aria-hidden="true">&#8594;</b></div>
      <div>
        <span class="cv-tag">TARGET PROFILE / one row per pump</span>
        <div class="cv-table-scroll">
          <table class="cv-table">
            <thead><tr><th class="cv-key">cooling pump</th></tr></thead>
            <tbody><tr><td class="cv-key">P-01</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>

### Emerge

An operator introduces data at a target profile when no source profile exists.
The relationship is determined by the missing source profile, not by the
function's external data source.

<div class="concepts-visual">
  <div class="cv-operation" role="group" aria-label="Emerge grain relationship">
    <div class="cv-transform">
      <div>
        <span class="cv-tag">SOURCE PROFILE / absent</span>
        <div class="cv-table-scroll">
          <table class="cv-table">
            <thead><tr><th class="cv-key">source profile</th><th class="cv-key">grain</th></tr></thead>
            <tbody><tr><td class="cv-key">none</td><td class="cv-key">none</td></tr></tbody>
          </table>
        </div>
      </div>
      <div class="cv-arrow"><span>emerge</span><b aria-hidden="true">&#8594;</b></div>
      <div>
        <span class="cv-tag">TARGET PROFILE / one row per pump and timestamp</span>
        <div class="cv-table-scroll">
          <table class="cv-table">
            <thead><tr><th class="cv-key">cooling pump</th><th class="cv-key">timestamp</th></tr></thead>
            <tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>

### Vanish

An operator consumes data from a source profile without producing a target
profile. The relationship describes the profile boundary, not the destination
of any external write.

<div class="concepts-visual">
  <div class="cv-operation" role="group" aria-label="Vanish grain relationship">
    <div class="cv-transform">
      <div>
        <span class="cv-tag">SOURCE PROFILE / one row per pump and timestamp</span>
        <div class="cv-table-scroll">
          <table class="cv-table">
            <thead><tr><th class="cv-key">cooling pump</th><th class="cv-key">timestamp</th></tr></thead>
            <tbody><tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td></tr><tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td></tr></tbody>
          </table>
        </div>
      </div>
      <div class="cv-arrow"><span>vanish</span><b aria-hidden="true">&#8594;</b></div>
      <div>
        <span class="cv-tag">TARGET PROFILE / absent</span>
        <div class="cv-table-scroll">
          <table class="cv-table">
            <thead><tr><th class="cv-key">target profile</th><th class="cv-key">grain</th></tr></thead>
            <tbody><tr><td class="cv-key">none</td><td class="cv-key">none</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>
