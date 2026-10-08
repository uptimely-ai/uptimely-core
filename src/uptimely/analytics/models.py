from dataclasses import dataclass, field

from uptimely.spec import Function


def _filled_fields(**fields: object) -> dict:
    """Return fields with values useful for graph rendering."""
    return {key: value for key, value in fields.items() if value is not None}


@dataclass(frozen=True)
class FunctionNode:
    """Display metadata for one function node and its resolved function template."""

    name: str
    feature: str | None
    entity: str
    function: Function | None = field(default=None, compare=False, hash=False)
    operation_id: str | None = None

    @property
    def node_id(self) -> str:
        """Stable graph identifier for this function invocation."""
        operation_id = self.operation_id or self.feature or self.name
        function_type = self.function.role if self.function is not None else "unknown"
        return f"function:{self.entity}:{function_type}:{operation_id}"

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def to_render_data(self, node_type: str = "function") -> dict:
        """Return display metadata for rendering this function node."""
        return _filled_fields(
            node_type=node_type,
            is_function=True,
            label=self.name,
            feature=self.feature,
            entity=self.entity,
            operation_id=self.operation_id,
            function_type=(
                "vectorize"
                if self.function is not None and self.function.role == "analytics"
                else self.function.role
                if self.function is not None
                else None
            ),
            type=self.function.type if self.function is not None else None,
            entrypoint=self.function.entrypoint if self.function is not None else None,
            info=self.function.info if self.function is not None and self.function.info else None,
        )


@dataclass(frozen=True)
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

    def to_render_data(self, node_type: str) -> dict:
        """Return display metadata for rendering this feature node."""
        return _filled_fields(
            node_type=node_type,
            is_function=False,
            label=self.name,
            entity=self.entity,
            data_type=self.data_type,
        )
