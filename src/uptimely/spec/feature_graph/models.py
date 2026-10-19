import dataclasses

from uptimely import render
from uptimely.spec import model


@dataclasses.dataclass(frozen=True)
class FunctionNode:
    """Display metadata for one declared function template."""

    name: str
    features: tuple[str, ...]
    entity: str | None
    function: model.FunctionTemplate | None = dataclasses.field(
        default=None, compare=False, hash=False
    )

    @property
    def node_id(self) -> str:
        """Stable graph identifier for this function definition."""
        function_type = (
            "spec"
            if self.function is not None and self.function.operation == "vectorize"
            else self.function.operation
            if self.function is not None
            else "unknown"
        )
        return f"function:{function_type}:{self.name}"

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def to_render_data(self, node_type: str = "function") -> dict[str, object]:
        """Return display metadata for rendering this function node."""
        return render.filled_fields(
            node_type=node_type,
            is_function=True,
            label=self.name,
            features=list(self.features),
            entity=self.entity,
            function_type=(self.function.operation if self.function is not None else None),
            type="python_function" if self.function is not None else None,
            entrypoint=self.function.entrypoint if self.function is not None else None,
            info={"description": self.function.description} if self.function is not None else None,
        )


@dataclasses.dataclass(frozen=True)
class FeatureNode:
    """Display metadata for a feature name and its logical metadata."""

    name: str
    data_type: str | None = None
    entity: str | None = None
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

    def to_render_data(self, node_type: str) -> dict[str, object]:
        """Return display metadata for rendering this feature node."""
        return render.filled_fields(
            node_type=node_type,
            is_function=False,
            label=self.name,
            entity=self.entity,
            data_type=self.data_type,
        )
