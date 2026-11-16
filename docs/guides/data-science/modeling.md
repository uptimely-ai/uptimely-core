# Organize calculations by profile

## Organizing calculations by profile

A data-center operator might want to detect overheating for different kinds of cooling equipment.

For example, `Energy` for one machine Category might be a directly available
measurement, while another Category's value requires basic calculation, and a third one more specialized neural network.

Putting all such behavior into one broad calculation can obscure differences
in grain, machine behavior, and business rules.

This creates a conflict between analytical requirements and how dimensional modeling works.

Dimensional modeling is designed for data storage.
It mostly expects that `overheating_alarm` is always calculated with same logic.
But that is not how the world works.

Because it does not consider the analytical subsets, the code starts to fall apart by hardcoding the exceptions:

```txt
if category = A
    function_a()
elif category = B
    run_function_b()
elif machine = 001
    very_complex_override_logic()
```

In SQL this would be even more unmanageable.

The fact is that machine in category A might have different measurements than category B.

Then you calculate `overheating_alarm_category_a` in category A profile and `overheating_alarm_category_b` in category B profile. And for outlier machines you might have `overheating_alarm_machine` in machine grained profile.

This is manageable and mathematically correct. The decision whether you want all of them resolve logically to a single `overheating_alarm` feature is up to you.
