# Spec: Operators

## Operator

An operator describes the inputs and outputs of one calculation and names the
function that performs it. Each key under the profile's `assembly` object
identifies one operator. Do not include an `id` field. The key names this
calculation, not a reusable function or output feature. Multiple operators can
use the same function with different arguments.

In Python authoring and JSON, every operator has a `compute` binding and may
have a `merge` binding. Function signatures, dataframe arguments, the profile's
seed reference, and the presence of a merge determine execution contracts.
Read, transform, write, and workflow describe function signatures, not operator
attributes.

| Field | JSON type | Selector | Required | Default | Meaning |
| --- | --- | --- | --- | --- | --- |
| `interface` | object | No | No | Empty lists | Explicit prerequisites and outputs. |
| `interface.inputs` | array of strings | Yes | No | `[]` | Features that must be available before the function runs. |
| `interface.outputs` | array of strings | Yes | No | `[]` | Features produced in the owning profile. |
| `row_context` | object or null | No | No | `null` | Surrounding-observation requirements. |
| `compute` | object | No | Yes | N/A | Function call. |
| `compute.function` | string | No | Yes | N/A | ID of the function to call. Use the function ID without a selector. |
| `compute.args` | object | Yes | No | `{}` | Values passed to the function. |
| `is_workflow` | boolean | No | No | `false` | Marks an opaque workflow without dataframe inputs or outputs. Python authoring derives it for non-dataframe functions with no dataframe input. |
| `merge` | object or null | No | No | `null` | Optional function that combines the current dataset with the compute result. |
| `merge.function` | string | No | Yes when `merge` is set | N/A | ID of the function that combines the data. |
| `merge.args` | object | Yes | No | `{}` | Arguments including the current dataset and the compute result. |

### Compute

`compute.args` supplies values to the function named in `compute.function`.
The function accepts at most one top-level dataframe argument. Its dataframe
result is the complete target without a merge, or a fragment with a merge.
Ignored results do not relax the dataframe limit.

### Feature interface

Input and output lists contain distinct `$features.<id>` references. Inputs
list the features the calculation reads, even when they are not passed as
arguments. Do not list identifiers or relations there. Declare those through
the profile's `grain` and `relations`. Passing a feature name as an argument
does not list it as an input. The `inputs` list describes features needed by
the compute function, not data used by the merge function.

Outputs must name features declared for the profile. They are the only way to
declare which features an operator produces. Passing a feature name as an
argument does not declare it as an input or output. A target dataframe must
include all target dimension keys and the operator's declared outputs. A
column transform of an existing target dataframe must retain its existing
columns.

A publish operator has no outputs and lists its required inputs. Its function
can receive a dataframe or read the needed data internally. External writes
do not create profile dataframe columns. Other operators
that produce data must declare at least one feature output, except source
readers that provide only profile identifiers or relations. A collapse
relationship must produce at least one feature. The function declaration
specifies its return contract.

When a merge is declared, the compute result is a fragment. It must include the
target keys available in its source profile and the operator's declared
outputs. For an `expand` relationship, the fragment may omit target keys that its
source profile does not have. See the [Engine guide](../intro/dataframes.md#datasets-and-fragments)
for details on combining and checking fragments.

Use selectors in `compute.args` only where the argument accepts them. See
[Selectors](spec-selectors.md#selectors) for supported references and their value types.

### Merge

Use merge to integrate a dataframe fragment into the current dataset.
Seeds must not merge. Complete-target updates need no merge, and functions
without dataframe results cannot merge. Foreign feature dependencies alone
do not require one.

The merge is optional, but declare it explicitly. Its function must accept
exactly two dataframe arguments, `dataset` and `fragment`. It may also accept
other arguments. Set `dataset` to `$profiles.@.dataset` and `fragment` to
`$operators.@.fragment`. Before the first merge, `dataset` may be null. The
function must return a dataframe containing the accumulated dataset and
fragment columns, with no additional columns. Merge arguments cannot reference
features.

The built-in `merge_by_grain`, exposed as `merge.default()` in Python, aligns
rows by target grain keys. Omission never selects it implicitly. See the
[Engine guide](../intro/dataframes.md#fragments-and-datasets) for details.

### Grain relationships

Explorer derives [grain relationships](../intro/grain-relationships.md#grain-relationships)
from dimension resolutions. These are not function classifications or Spec
fields. They neither perform calculations nor select a merge.

### Row Context

`row_context` belongs to the operator, not its features or function
declaration. It describes how much surrounding input data its calculations
need. It does not change which rows a function returns or limit execution to a
subset of rows.

| Field | JSON type | Selector | Required | Default | Meaning |
| --- | --- | --- | --- | --- | --- |
| `dimension` | string | Yes | Conditional | N/A | Reference to a declared input dimension. Required for `time` or `steps`. |
| `before` | object, string, or integer | No | No | `{}` | Required preceding context. A nonnegative integer is a row-count shorthand. |
| `after` | object, string, or integer | No | No | `{}` | Required following context. A nonnegative integer is a row-count shorthand. |

Each direction can be an object with at most one of these measurements, the
string `"unbounded"`, or a nonnegative integer shorthand for a row count. When
both directions use a measurement, they must use the same one:

| Measurement | Allowed bound | Dimension |
| --- | --- | --- |
| `time` | Fixed duration, such as `"8h"`, or `"unbounded"`. | Datetime. |
| `steps` | Nonnegative integer or `"unbounded"`. | Integer. |
| `rows` | Nonnegative integer or `"unbounded"`. | None. Ordering follows the profile order. |

Only fixed time or step windows and row counts are supported. A window cannot
depend on feature values or on a size calculated from the data.

```json
"row_context": {
  "before": {"rows": 1},
  "after": {"rows": 0}
}
```

Omitting `row_context` or setting it to null means the required range is
unspecified. Empty or zero directions mean only the current row is needed. Two
unbounded directions require the whole input and no declared order. One
unbounded direction still requires an order. Functions handle grouping and
sorting themselves.

Nonzero directional requirements need a profile order. A time or step dimension
must belong to the input profile and have the matching type. If the context
requires ordering by that dimension, include it in the profile's `order`. For
operations that remove dimensions, checks use the source profile identified
from the inputs. Other operations use the target profile.

Fixed durations use these distinct lowercase suffixes:

| Suffix | Unit |
| --- | --- |
| `w` | Weeks (7 days) |
| `d` | Days (24 hours) |
| `h` | Hours |
| `m` | Minutes |
| `s` | Seconds |
| `ms` | Milliseconds |
| `us` | Microseconds |
| `ns` | Nanoseconds |

Durations are nonnegative, contain no whitespace, and have nanosecond or
coarser precision. A duration may combine units, such as `"1h30m"`, but may
use each unit suffix only once.

An eight-row rolling window including the current row needs seven preceding
rows. An eight-hour window ending two hours ago needs ten hours before.
The declaration must cover the data the calculation actually needs, not just
repeat its window parameter.
