import dataclasses

from uptimely.spec import model


@dataclasses.dataclass(frozen=True)
class ActionNode:
    """Graph metadata for one declared action and its bound function."""

    action_id: str
    features: tuple[str, ...]
    entity: str | None
    dataset_id: str
    action: model.Action | None = dataclasses.field(default=None, compare=False, hash=False)
    function: model.FunctionTemplate | None = dataclasses.field(
        default=None, compare=False, hash=False
    )

    @property
    def node_id(self) -> str:
        """Stable graph identifier for this action in its dataset."""
        entity = self.entity or ""
        return f"action:{entity}:{self.dataset_id}:{self.action_id}"

    def __str__(self) -> str:
        return self.action_id

    def __repr__(self) -> str:
        return str(self)


@dataclasses.dataclass(frozen=True)
class FeatureNode:
    """Graph metadata for a feature name and its logical metadata."""

    name: str
    data_type: str | None = None
    entity: str | None = None
    dataset_id: str | None = None
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
