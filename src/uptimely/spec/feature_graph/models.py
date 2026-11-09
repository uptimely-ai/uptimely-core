import dataclasses
import typing

from uptimely.spec import model


@dataclasses.dataclass(frozen=True)
class OperatorNode:
    """Graph metadata for one declared operator and its bound function."""

    operator_id: str
    features: tuple[str, ...]
    profile_id: str
    function: model.FunctionTemplate = dataclasses.field(compare=False, hash=False)
    execution_form: str
    binding_roles: tuple[str, ...]
    grain_relationships: tuple[tuple[str | None, str], ...]
    source_status: str
    function_returns: typing.Literal["dataframe", "none", "any"]
    profile_name: str | None = None
    operator: model.Operator | None = dataclasses.field(default=None, compare=False, hash=False)

    @property
    def node_id(self) -> str:
        """Stable graph identifier for this operator in its profile."""
        return f"operator:{self.profile_id}:{self.operator_id}"

    def __str__(self) -> str:
        return self.operator_id

    def __repr__(self) -> str:
        return str(self)


@dataclasses.dataclass(frozen=True)
class FeatureNode:
    """Graph metadata for a feature name and its logical metadata."""

    name: str
    data_type: str | None = None
    profile_id: str | None = None
    display_name: str | None = None
    profile_name: str | None = None
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
