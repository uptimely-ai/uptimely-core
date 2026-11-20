from collections import abc

import pytest

from uptimely.codebase.python import codebase as codebase_module
from uptimely.codebase.python import entrypoint as shared_entrypoint

pytestmark = pytest.mark.usefixtures("example_projects")


@pytest.fixture(autouse=True)
def isolate_package_index() -> abc.Iterator[None]:
    """Keep mocked distribution indexes separate from real environment metadata."""
    shared_entrypoint.PackageOrigin.invalidate_cache()
    yield
    shared_entrypoint.PackageOrigin.invalidate_cache()


def test_python_codebase_indexes_unique_entrypoints_with_package_origins() -> None:
    package = shared_entrypoint.PackageOrigin("example-package", "1.2.3")

    codebase = codebase_module.Codebase.from_locations(
        ["math:ceil", "math:floor", "math:ceil"],
        {"math:ceil": package},
    )

    assert list(codebase.entrypoints_index) == ["math:ceil", "math:floor"]
    assert all(
        isinstance(implementation, shared_entrypoint.Entrypoint)
        for implementation in codebase.entrypoints_index.values()
    )
    assert codebase.entrypoints_index["math:ceil"].package is package
    assert codebase.entrypoints_index["math:floor"].package is None
    with pytest.raises(TypeError):
        codebase.entrypoints_index["other:call"] = shared_entrypoint.Entrypoint("other:call")  # type: ignore[index]
