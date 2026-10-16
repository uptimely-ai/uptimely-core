"""Runtime configuration for analytics plan execution."""

import dataclasses


@dataclasses.dataclass(frozen=True)
class EngineConfig:
    """Runtime configuration supplied to an execution engine.

    ``evaluation`` and ``batch_size`` are reserved and do not currently affect
    execution.
    """

    type: str = "python_venv"
    definition: str | None = None
    dataframe: str = "polars"
    evaluation: str = "eager"
    batch_size: int | str | None = None

    def __post_init__(self) -> None:
        """Validate configuration values before execution begins."""
        if not isinstance(self.dataframe, str) or self.dataframe.lower() != "polars":
            raise ValueError(
                "Unsupported dataframe backend: "
                f"{self.dataframe}. Version 0.1 supports only polars."
            )
        if self.batch_size is not None and (
            not (
                isinstance(self.batch_size, int)
                and not isinstance(self.batch_size, bool)
                and self.batch_size > 0
            )
            and self.batch_size != "*"
        ):
            raise ValueError("batch_size must be a positive integer, '*', or None")
