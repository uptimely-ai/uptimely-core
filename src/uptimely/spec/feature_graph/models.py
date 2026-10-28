import dataclasses

from uptimely.spec import functions, model


@dataclasses.dataclass(frozen=True)
class FunctionNode:
    """Graph metadata for one declared function template."""

    name: str
    features: tuple[str, ...]
    entity: str | None
    action_id: str | None = None
    function: model.FunctionTemplate | None = dataclasses.field(
        default=None, compare=False, hash=False
    )

    @property
    def node_id(self) -> str:
        """Stable graph identifier for this function definition."""
        function_kind = (
            "spec"
            if self.function is not None and self.function.kind == functions.VECTORIZE
            else self.function.kind
            if self.function is not None
            else "unknown"
        )
        action = f":{self.action_id}" if self.action_id is not None else ""
        return f"function:{function_kind}:{self.name}{action}"

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name


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
