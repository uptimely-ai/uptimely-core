"""Implementations loaded from an installed package, not a project directory."""

import polars


class Readers:
    """Expose a qualified callable name for import regression coverage."""

    @staticmethod
    def values() -> polars.DataFrame:
        """Return deterministic data for execution assertions."""
        return polars.DataFrame({"row": [1, 2], "value": [2, 3]})
