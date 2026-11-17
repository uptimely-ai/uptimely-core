# Organize calculations by profile

## Why one calculation can fall short

A data center operator might want to detect overheating for different kinds of cooling equipment.

For example, `Energy` for one machine Category might be a directly available
measurement, while another Category's value requires basic calculation, and a third one more specialized neural network.

Putting all such behavior into one broad calculation can obscure differences
in grain, machine behavior, and business rules.

This creates a conflict between analytical requirements and how dimensional modeling works.

## Profiles and dimensional modeling

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

Now you have single computation that hides all that dimensional complexity.

In SQL syntax this would be even more unmanageable.

## Match calculations to profiles

The fact is that machine in category A might have different measurements than category B.

Then you calculate `overheating_alarm_category_a` in category A profile and `overheating_alarm_category_b` in category B profile. And for an outlier machine, you might even have `overheating_alarm_machine_001` in machine specific profile.

This is manageable and follow dimensional modeling. The decision whether you want all of them resolve logically to a single `overheating_alarm` feature is up to you. At the moment, consolidating semantically same meaning features is not in the scope of Uptimely responsibilities.
