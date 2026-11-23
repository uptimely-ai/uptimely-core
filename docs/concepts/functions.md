# Functions and contracts


A **function** is reusable code with typed arguments and a declared return
contract.

Function implementationsa are independent from spec's logical function templates. This makes it possible to keep the spec unthouched while changing the implementation on the background.

## Function dataframe signature

The inspector derives and validates the number of dataframes an implementation
takes as arguments and returns. The Spec stores the logical dataframe contract.

Dataframe counts describe the function data signature, independently of operator
bindings, logical features, or internal I/O.

| Dataframes in → out | Semantic label |
| --- | --- |
| 0 → 1 | `read` |
| 1 → 1 | `transform` |
| 1 → 0 | `write` |
| 2 → 1 | `combine` |
| x → x | `workflow` |

The labels are derived as function semantics, and developer does not need to define them by hand.

Dataframe signatures visualized:

<div class="concepts-visual">
  <div class="cv-contracts" role="group" aria-label="Function contracts by dataframe inputs and outputs">
    <div class="cv-contract">
      <span class="cv-tag">READ 0&#8594;1</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot cv-slot-empty">no input</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot">dataframe</span></div></div>
      <p>Returns a dataframe without receiving a framework-bound dataframe.</p>
    </div>
    <div class="cv-contract">
      <span class="cv-tag">TRANSFORM 1&#8594;1</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot">dataframe</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot">dataframe</span></div></div>
      <p>Transforms a dataframe into a new dataframe or fragment.</p>
    </div>
    <div class="cv-contract">
      <span class="cv-tag">WRITE 1&#8594;0</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot">dataframe</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot cv-slot-empty">no output</span></div></div>
      <p>Consumes a dataframe for a side effect, such as a write.</p>
    </div>
    <div class="cv-contract">
      <span class="cv-tag">WORKFLOW ?&#8594;?</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot cv-slot-empty">unknown input</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot cv-slot-empty">unknown output</span></div></div>
      <p>The ignored-result contract does not describe internal dataframe use.</p>
    </div>
    <div class="cv-contract cv-contract-combine">
      <span class="cv-tag">COMBINE 2&#8594;1</span>
      <div class="cv-contract-flow"><div class="cv-slots"><span class="cv-slot">dataset</span><span class="cv-slot">fragment</span></div><b aria-hidden="true">&#8594;</b><div class="cv-fn">function</div><b aria-hidden="true">&#8594;</b><div class="cv-slots"><span class="cv-slot">dataframe</span></div></div>
      <p>Combines the current dataset with a computed fragment.</p>
    </div>
  </div>
</div>

## Other arguments

Functions might have any additional arguments. Spec validation checks declared
argument names and types. Binding inspection additionally compares these
declarations with implementation parameters and annotations.
