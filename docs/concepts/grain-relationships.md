# Grain relationships

## Derived grain relationships

Explorer reports source-to-target relationships inferred from profile grains
and their dimension hierarchies. These values are not stored in the Spec or
portable execution plan.

An absent source profile is reported as `emerge`, while an absent target profile
is reported as `vanish`. These are distinct from comparing a declared profile
with an empty grain. If both profiles are absent, no comparison applies.

| Relationship | Source compared with target |
| --- | --- |
| `same` | Both select the same dimensions and resolutions. |
| `expand` | The target refines the source by adding dimensions or selecting finer resolutions. |
| `collapse` | The target is coarser by removing dimensions or selecting coarser resolutions. |
| `emerge` | No source profile exists; the operator introduces data at the target grain. |
| `vanish` | No target profile exists; the operator consumes the source grain without producing a profile. |
| `unrelated` | Neither grain refines the other through the declared hierarchy. |
| `not_applicable` | A declared source cannot be resolved, or a profile grain is invalid. |

The comparison uses resolution hierarchy, not dimension counts. Sources include
logical feature owners and dataframe profiles. These labels do not perform
calculations or select a merge.
