import dataclasses

from uptimely.explorer import render
from uptimely.spec import model, operations


@dataclasses.dataclass(frozen=True)
class FunctionNode:
    """Display metadata for one declared function template."""

    name: str
    features: tuple[str, ...]
    entity: str | None
    mapping_id: str | None = None
    function: model.FunctionTemplate | None = dataclasses.field(
        default=None, compare=False, hash=False
    )

    @property
    def node_id(self) -> str:
        """Stable graph identifier for this function definition."""
        function_kind = (
            "spec"
            if self.function is not None and self.function.kind == operations.VECTORIZE
            else self.function.kind
            if self.function is not None
            else "unknown"
        )
        mapping = f":{self.mapping_id}" if self.mapping_id is not None else ""
        return f"function:{function_kind}:{self.name}{mapping}"

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def to_render_data(self, node_type: str = "function") -> dict[str, object]:
        """Return display metadata for rendering this function node."""
        return render.filled_fields(
            node_type=node_type,
            is_function=True,
            label=f"{self.name} · {self.mapping_id}" if self.mapping_id is not None else self.name,
            mapping_id=self.mapping_id,
            features=list(self.features),
            entity=self.entity,
            function_kind=(self.function.kind if self.function is not None else None),
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
