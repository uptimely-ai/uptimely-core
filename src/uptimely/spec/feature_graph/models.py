import dataclasses

from uptimely.spec import model


@dataclasses.dataclass(frozen=True)
class ActionNode:
    """Graph metadata for one declared action and its bound function."""

    action_id: str
    features: tuple[str, ...]
    profile_id: str
    dataset_id: str
    function: model.FunctionTemplate = dataclasses.field(compare=False, hash=False)
    dataset_name: str | None = None
    action: model.Operator | None = dataclasses.field(default=None, compare=False, hash=False)

    @property
    def node_id(self) -> str:
        """Stable graph identifier for this action in its dataset."""
        return f"action:{self.profile_id}:{self.action_id}"

    def __str__(self) -> str:
        return self.action_id

    def __repr__(self) -> str:
        return str(self)


@dataclasses.dataclass(frozen=True)
class FeatureNode:
    """Graph metadata for a feature name and its logical metadata."""

    name: str
    data_type: str | None = None
    profile_id: str | None = None
    dataset_id: str | None = None
    display_name: str | None = None
    dataset_name: str | None = None
    is_input: bool = False
    is_output: bool = False
    is_source_input: bool = False

    @property
    def node_id(self) -> str:
        """Stable graph identifier for this feature."""
        return self.name

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    @property
    def is_intermediate(self) -> bool:
        """Whether this feature is both produced and consumed by the graph."""
        return self.is_input and self.is_output
