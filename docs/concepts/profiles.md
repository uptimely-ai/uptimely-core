# Profiles and features

## Profile

<p class="cv-function-subtitle">A selected grain and its available features</p>

A profile is more than data. It is an analytical specification with three parts:

- A **scope** that describes what the profile covers.
- A set of **analytical operators** that produce and transform its features.
- A **unique set of features**. Each feature belongs to exactly one profile and has exactly one producing operator.

A profile selects one resolution per dimension in its ordered `grain`. This
profile selects cooling-pump and timestamp keys for minute-by-minute observations.

`Seed` identifies the dataset initializer, which can read data or
transform another profile. It returns the complete target without a merge or
an existing target input.

Other profiles could represent:

| Profile | What one row represents | Example features |
| --- | --- | --- |
| Cooling-pump reference data | One cooling pump | Rated flow, installation date |
| Minute-level telemetry | One cooling pump at one timestamp | Differential pressure, flow |
| Daily cooling-pump summaries | One cooling pump on one day | Maximum differential pressure, average flow |
| Maintenance events | One maintenance event for a cooling pump | Event type, downtime |

Note that this is analytical representation.
Data might be stored physically in different way.

<div class="concepts-visual">
  <div class="cv-profile">
    <div class="cv-scope">
      <div><span>GRAIN</span><strong>One cooling pump at one timestamp</strong></div>
      <div><span>SCOPE / DESCRIPTIVE ONLY</span><strong>Data-center cooling pump observations</strong></div>
      <div><span>CATEGORY</span><strong>Telemetry</strong></div>
    </div>
    <div class="cv-table-scroll">
      <table class="cv-table cv-model-table">
        <thead>
          <tr class="cv-bands"><th colspan="2" class="cv-key">DIMENSIONS / observation keys</th><th colspan="2" class="cv-teal">TELEMETRY / operator A</th><th class="cv-violet">LIMITS / operator B</th><th class="cv-amber">CALCULATED</th></tr>
          <tr><th class="cv-key">cooling pump</th><th class="cv-key">timestamp</th><th class="cv-teal">differential pressure</th><th class="cv-teal">flow</th><th class="cv-violet">limit</th><th class="cv-amber">ratio</th></tr>
        </thead>
        <tbody>
          <tr><td class="cv-key">P-01</td><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-teal">12</td><td class="cv-violet">8</td><td class="cv-amber">0.75</td></tr>
          <tr><td class="cv-key">P-01</td><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-teal">14</td><td class="cv-violet">8</td><td class="cv-amber">1.00</td></tr>
          <tr><td class="cv-key">P-01</td><td class="cv-key">09:02</td><td class="cv-teal">4</td><td class="cv-teal">10</td><td class="cv-violet">8</td><td class="cv-amber">0.50</td></tr>
        </tbody>
      </table>
    </div>
    <p class="cv-legend-title">Color key</p>
    <ul class="cv-legend-row">
      <li><span class="cv-swatch cv-key" aria-hidden="true"></span>Dimension keys</li>
      <li><span class="cv-swatch cv-teal" aria-hidden="true"></span>Telemetry features</li>
      <li><span class="cv-swatch cv-violet" aria-hidden="true"></span>Limit features</li>
      <li><span class="cv-swatch cv-amber" aria-hidden="true"></span>Calculated features</li>
    </ul>
  </div>
</div>

The combined profile dataframe is a conceptual view, not a requirement to store all
intermediate columns in one physical table.
