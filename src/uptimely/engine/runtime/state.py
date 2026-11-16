"""Per-execution state and lookups for portable plan execution."""

import dataclasses

from uptimely import plan as plan_module
from uptimely.engine.dataframe import dataset as dataset_module
from uptimely.engine.dataframe import fragment as fragment_module


@dataclasses.dataclass
class RuntimeState:
    """Materialized profile datasets, retained fragments, and outputs for one run."""

    datasets: dict[str, dataset_module.Dataset] = dataclasses.field(default_factory=dict)
    computed_fragments: dict[str, fragment_module.Fragment] = dataclasses.field(
        default_factory=dict
    )
    calculated_outputs: dict[tuple[str, str], object] = dataclasses.field(default_factory=dict)

    def computed_fragment_for(
        self, invocation: plan_module.Invocation
    ) -> tuple[str, fragment_module.Fragment]:
        """Find the single computed fragment dependency of a merge invocation.

        Raises:
            ValueError: The invocation does not depend on exactly one computed fragment.
        """
        dependencies = [
            dependency_id
            for dependency_id in invocation.dependency_ids
            if dependency_id in self.computed_fragments
        ]
        if len(dependencies) != 1:
            raise ValueError(
                f"Merge invocation {invocation.id} requires exactly one "
                "computed fragment dependency"
            )
        dependency_id = dependencies[0]
        return dependency_id, self.computed_fragments[dependency_id]

    def resolve_dataset_or_fragment_dataframe(self, identifier: str) -> object | None:
        """Resolve a materialized dataset ID or fragment mapping ID to its dataframe.

        Dataset IDs take precedence over fragment names.

        Args:
            identifier: Dataset ID or fragment mapping ID.

        Returns:
            The underlying dataframe, or None when neither kind of reference exists.

        Raises:
            ValueError: A fragment name matches multiple datasets.
        """
        dataset = self.datasets.get(identifier)
        if dataset is not None:
            return dataset.dataframe
        matches = [
            dataset.fragments[identifier].dataframe
            for dataset in self.datasets.values()
            if identifier in dataset.fragments
        ]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous fragment reference: {identifier}")
        return matches[0] if matches else None
