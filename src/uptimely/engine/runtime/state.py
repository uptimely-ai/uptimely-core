"""Per-execution state and lookups for portable plan execution."""

import dataclasses


@dataclasses.dataclass
class RuntimeState:
    """Mutable outputs and dataframe references for one plan execution."""

    datasets: dict[str, object] = dataclasses.field(default_factory=dict)
    fragments: dict[tuple[str, str], object] = dataclasses.field(default_factory=dict)
    calculated_outputs: dict[tuple[str, str], object] = dataclasses.field(default_factory=dict)

    def dataframe_by_id(self, identifier: str) -> object | None:
        """Return a unique dataset or fragment, preferring datasets by ID."""
        dataset = self.datasets.get(identifier)
        if dataset is not None:
            return dataset
        matches = [
            frame for (_, fragment_id), frame in self.fragments.items() if fragment_id == identifier
        ]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous fragment reference: {identifier}")
        return matches[0] if matches else None
