from __future__ import annotations

import dataclasses

from uptimely import row_context
from uptimely.spec import operations


@dataclasses.dataclass(frozen=True)
class CallableNode:
    """One fragment, calculation, or sink function invocation."""

    function_id: str
    entity: str
    feature: str | None = None
    operation: operations.FunctionOperation = operations.VECTORIZE
    dataset_id: str | None = None
    mapping_id: str | None = None
    output_features: tuple[str, ...] = ()
    args: dict[str, object] = dataclasses.field(default_factory=dict, compare=False, hash=False)
    input_features: tuple[str, ...] = ()
    row_context: row_context.RowContext | None = dataclasses.field(
        default=None, compare=False, hash=False
    )

    @property
    def node_id(self) -> str:
        """Stable graph identifier for this callable invocation."""
        identifier = self.mapping_id or self.feature or self.function_id
        return (
            f"callable:{self.operation}:{self.function_id}:"
            f"{self.entity}:{self.dataset_id}:{identifier}"
        )

    def __str__(self) -> str:
        return f"{self.function_id}({self.entity})"

    def __repr__(self) -> str:
        return f"{self.function_id}({self.entity})"
