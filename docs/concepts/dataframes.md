# Datasets and fragments

## Datasets and fragments

A runtime Dataset is the Engine's accumulated dataframe for a profile defined in spec. As invocations run, the Engine
provides datasets to functions and updates them with produced results.

Without a merge, a returned dataframe becomes the complete target. With a
merge, it is staged as a fragment. Current-target updates preserve existing
rows, keys, values, and order.

In the picture below, direct updates are yellow and fragment-producing calls
are gray, except for the write invocation.

![Engine dataset accumulation across function invocations](../assets/img/engine-dataset-accumulation.png)

### Fragment and merge

A fragment is the partial dataframe produced by some data-producing compute
invocations. The Engine stages it without immediately changing the accumulated
Dataset. A separate merge invocation combines the fragment with the Dataset and
publishes the resulting complete dataframe. The built-in merge uses declared
dimension identifiers to align rows rather than relying on row position.
Depending on the fragment grain, it can combine full-grain data or add
lower-grain values to matching rows. A custom merge function can define
different assembly behavior. Feature consumers wait for the merge to succeed.
Omitting a merge never selects the built-in merge implicitly.

### Publication

Publish operations use compute with input dependencies and no output features.
Opaque workflows may read and write internally, but their results are not added
to profile dataframes. Logical workflow outputs establish dependencies only.
