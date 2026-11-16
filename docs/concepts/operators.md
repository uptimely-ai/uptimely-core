# Operators and bindings

## Operator

<p class="cv-function-subtitle">Connect feature dependencies and outputs to a function binding</p>

Every operator has one `compute` binding and optionally a `merge` binding.
See [Datasets and fragments](dataframes.md) for result handling and publication,
and [Function contracts](functions.md#function-contracts) for dataframe limits.

In this example, the operator declares its features and binds `divide` to the
current dataframe and feature identifiers.

<div class="concepts-visual">
  <div class="cv-operation cv-mapping-flow" role="group" aria-label="Input dataframe, Python operator, and output dataframe">
    <div class="cv-mapping-stage cv-mapping-inputs">
      <span class="cv-tag">INPUT DATAFRAME / declared features</span>
      <table class="cv-table"><thead><tr><th class="cv-key">time</th><th class="cv-teal">pressure</th><th class="cv-violet">limit</th></tr></thead><tbody><tr><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-violet">8</td></tr><tr><td class="cv-key">09:02</td><td class="cv-teal">4</td><td class="cv-violet">8</td></tr></tbody></table>
    </div>
    <div class="cv-mapping-arrow" aria-hidden="true">&#8595;</div>
    <div class="cv-mapping-stage cv-mapping-call">
      <span class="cv-tag">OPERATOR / PRESSURE RATIO</span>
      <p>Declares pressure and limit as inputs and pressure ratio as its output.
      Binds the divide function to the dataset and feature identifiers.</p>
    </div>
    <div class="cv-mapping-arrow" aria-hidden="true">&#8595;</div>
    <div class="cv-mapping-stage cv-mapping-outputs">
      <span class="cv-tag">OUTPUT DATAFRAME / declared feature</span>
      <table class="cv-table"><thead><tr><th class="cv-key">time</th><th class="cv-teal">pressure</th><th class="cv-violet">limit</th><th class="cv-amber">pressure_ratio</th></tr></thead><tbody><tr><td class="cv-key">09:00</td><td class="cv-teal">6</td><td class="cv-violet">8</td><td class="cv-amber">0.75</td></tr><tr><td class="cv-key">09:01</td><td class="cv-teal">8</td><td class="cv-violet">8</td><td class="cv-amber">1.00</td></tr><tr><td class="cv-key">09:02</td><td class="cv-teal">4</td><td class="cv-violet">8</td><td class="cv-amber">0.50</td></tr></tbody></table>
    </div>
    <p class="cv-takeaway"><strong>Two complementary declarations.</strong> Feature inputs and outputs describe data dependencies. Compute arguments provide the dataframe and feature identifiers the function uses. An identifier argument alone does not declare an input dependency.</p>
  </div>
</div>
