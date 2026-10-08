from dataclasses import dataclass, field

from uptimely.spec import Call

FRAGMENT_OPERATION_TYPES = frozenset({"read", "collapse", "expand", "conform"})
SOURCE_OPERATION_TYPES = FRAGMENT_OPERATION_TYPES


def _filled_fields(**fields: object) -> dict:
    """Return fields with values useful for graph rendering."""
    return {key: value for key, value in fields.items() if value is not None}


@dataclass(frozen=True)
class CallableNode:
    """One fragment, calculation, or sink function invocation."""

    function_id: str
    entity: str
    feature: str | None = None
    operation_type: str = "vectorize"
    dataset_id: str | None = None
    operation_id: str | None = None
    args: dict[str, object] = field(default_factory=dict, compare=False, hash=False)
    callable: Call | None = field(default=None, compare=False, hash=False)
    callable_type_override: str | None = field(default=None, compare=False, hash=False)

    @property
    def callable_type(self) -> str:
        """Return the specification function category for this operation."""
        if self.callable_type_override is not None:
            return self.callable_type_override
        return {
            "read": "read",
            "vectorize": "vectorize",
            "write": "write",
        }.get(self.operation_type, self.operation_type)

    @property
    def node_id(self) -> str:
        """Stable graph identifier for this callable invocation."""
        identifier = self.feature or self.operation_id or self.function_id
        return (
            f"callable:{self.operation_type}:{self.function_id}:"
            f"{self.entity}:{self.dataset_id}:{identifier}"
        )

    def __str__(self) -> str:
        return f"{self.function_id}({self.entity})"

    def __repr__(self) -> str:
        return f"{self.function_id}({self.entity})"

    def to_render_data(self, node_type: str = "callable") -> dict:
        """Return display metadata for rendering this callable node."""
        return _filled_fields(
            node_type=node_type,
            operation_type=self.operation_type,
            callable_type=self.callable_type,
            label=str(self),
            function_id=self.function_id,
            entity=self.entity,
            dataset_id=self.dataset_id,
            feature=self.feature,
            depends_on_features=(
                self.callable.depends_on_features if self.callable is not None else None
            ),
        )
