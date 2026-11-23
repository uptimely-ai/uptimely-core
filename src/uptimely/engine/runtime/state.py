"""Named values produced during one plan execution."""

import dataclasses


@dataclasses.dataclass
class RuntimeState:
    """Single-assignment values produced by invocation calls."""

    values: dict[str, object] = dataclasses.field(default_factory=dict)

    def store(self, name: str, value: object) -> None:
        """Store a named return without overwriting an earlier value.

        Raises:
            ValueError: The return name has already been assigned.
        """
        if name in self.values:
            raise ValueError(f"Return name is assigned more than once: {name}")
        self.values[name] = value

    def resolve(self, name: str) -> object:
        """Resolve a named return, including a return whose value is None.

        Raises:
            ValueError: The named return has not been produced.
        """
        if name not in self.values:
            raise ValueError(f"Return is unavailable: {name}")
        return self.values[name]
