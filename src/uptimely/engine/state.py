"""Per-execution state and lookups for portable plan execution."""

import dataclasses


@dataclasses.dataclass
class RuntimeState:
    """Mutable outputs and dataframe references for one plan execution."""

    datasets: dict[tuple[str, str], object] = dataclasses.field(default_factory=dict)
    fragments: dict[tuple[str, str], object] = dataclasses.field(default_factory=dict)
    calculated_outputs: dict[tuple[str, str, str], object] = dataclasses.field(default_factory=dict)

    def dataset_by_id(self, dataset_id: str) -> object | None:
        """Return a unique dataset by ID, rejecting ambiguous references."""
        matches = [
            frame for (_, current_id), frame in self.datasets.items() if current_id == dataset_id
        ]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous dataset reference: {dataset_id}")
        return matches[0] if matches else None

    def dataframe_by_id(self, identifier: str) -> object | None:
        """Return a unique dataset or fragment, preferring datasets by ID."""
        dataset = self.dataset_by_id(identifier)
        if dataset is not None:
            return dataset
        matches = [
            frame for (_, fragment_id), frame in self.fragments.items() if fragment_id == identifier
        ]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous fragment reference: {identifier}")
        return matches[0] if matches else None
