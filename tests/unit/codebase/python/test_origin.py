import pathlib
import sys
import types
from collections import abc

import polars
import pytest
from support import examples as example_support

from uptimely import compiler, spec
from uptimely.codebase.python import entrypoint as shared_entrypoint
from uptimely.codebase.python import origin

SPEC_PATH = example_support.EXAMPLES_ROOT / "artifacts/build/spec.json"


pytestmark = pytest.mark.usefixtures("example_projects")


@pytest.fixture(autouse=True)
def isolate_package_index() -> abc.Iterator[None]:
    """Keep mocked distribution indexes separate from real environment metadata."""
    shared_entrypoint.PackageOrigin.invalidate_cache()
    yield
    shared_entrypoint.PackageOrigin.invalidate_cache()


def test_source_origin_identifies_project_and_unknown_code(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "origin_project_fixture.py").write_text(
        "def calculate():\n    return 1\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(project_root))
    function = shared_entrypoint.Entrypoint("origin_project_fixture:calculate")

    assert function.read_source_origin(project_root) == shared_entrypoint.SourceOrigin("project")
    assert function.read_source_origin(tmp_path / "project-other") == (
        shared_entrypoint.SourceOrigin("unknown")
    )
    assert function.read_source_origin(None) == shared_entrypoint.SourceOrigin("unknown")
    assert shared_entrypoint.Entrypoint("builtins:len").read_source_origin(project_root) == (
        shared_entrypoint.SourceOrigin("unknown")
    )


def test_source_origin_identifies_installed_code_even_inside_project_root(
    tmp_path: pathlib.Path,
) -> None:
    assert polars.__file__ is not None
    installed_root = pathlib.Path(polars.__file__).resolve().parents[2]
    function = shared_entrypoint.Entrypoint("polars:thread_pool_size")
    expected = shared_entrypoint.SourceOrigin("third_party", "polars")

    assert function.read_source_origin(tmp_path) == expected
    assert function.read_source_origin(installed_root) == expected


def test_source_origin_without_project_root_does_not_import_module() -> None:
    function = shared_entrypoint.Entrypoint("unavailable_origin_fixture:calculate")

    assert function.read_source_origin(None) == shared_entrypoint.SourceOrigin("unknown")
    assert "unavailable_origin_fixture" not in sys.modules


def test_source_origin_follows_decorated_reexport(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "origin_decorated_fixture.py").write_text(
        "import functools\n"
        "import polars\n"
        "@functools.wraps(polars.thread_pool_size)\n"
        "def wrapped():\n"
        "    return polars.thread_pool_size()\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    origin = shared_entrypoint.Entrypoint("origin_decorated_fixture:wrapped").read_source_origin(
        tmp_path
    )

    assert origin == shared_entrypoint.SourceOrigin("third_party", "polars")


def test_package_provenance_uses_installed_metadata_without_importing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    distribution = types.SimpleNamespace(
        metadata={"Name": "fixture-distribution"},
        version="1.2.3",
    )
    monkeypatch.setattr(
        origin.importlib.metadata,
        "packages_distributions",
        lambda: {"fixture_package": ["fixture-distribution"]},
    )
    monkeypatch.setattr(
        origin.importlib.metadata,
        "distribution",
        lambda name: distribution if name == "fixture-distribution" else None,
    )

    provenance = shared_entrypoint.PackageOrigin.read("fixture_package.module")

    assert provenance == shared_entrypoint.PackageOrigin("fixture-distribution", "1.2.3")
    assert provenance.top_level_package == "fixture_package"
    assert provenance.distribution_candidates == ("fixture-distribution",)


def test_package_provenance_exposes_package_without_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        origin.importlib.metadata,
        "packages_distributions",
        lambda: {},
    )

    provenance = shared_entrypoint.PackageOrigin.read("fixture_package.module")

    assert provenance.distribution is None
    assert provenance.version is None
    assert provenance.top_level_package == "fixture_package"
    assert provenance.distribution_candidates == ()


@pytest.mark.parametrize(
    ("distribution", "version"),
    [("fixture-distribution", "1.2.3"), ("fixture-distribution", None), (None, None)],
)
def test_package_provenance_serializes_only_portable_metadata(
    distribution: str | None, version: str | None
) -> None:
    provenance = shared_entrypoint.PackageOrigin(
        distribution=distribution,
        version=version,
        top_level_package="fixture_package",
        distribution_candidates=("fixture-distribution",),
    )

    payload = provenance.to_dict()

    assert payload == {"distribution": distribution, "version": version}
    assert shared_entrypoint.PackageOrigin(**payload) == provenance


def test_package_provenance_rejects_ambiguous_namespaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        origin.importlib.metadata,
        "packages_distributions",
        lambda: {"shared_namespace": ["package-a", "package-b"]},
    )

    with pytest.raises(ValueError, match="Ambiguous installed package namespace"):
        shared_entrypoint.PackageOrigin.read("shared_namespace.module")


def test_package_index_is_scanned_once_across_modules_and_compilations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scans = 0

    def packages_distributions() -> dict[str, list[str]]:
        nonlocal scans
        scans += 1
        return {}

    monkeypatch.setattr(origin.importlib.metadata, "packages_distributions", packages_distributions)
    shared_entrypoint.PackageOrigin.read("first_package.module")
    shared_entrypoint.PackageOrigin.read("second_package.module")
    compiler.Compiler().compile(spec.load_spec(SPEC_PATH))
    compiler.Compiler().compile(spec.load_spec(SPEC_PATH))

    assert scans == 1


def test_package_index_refreshes_when_import_path_changes(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scans = 0

    def packages_distributions() -> dict[str, list[str]]:
        nonlocal scans
        scans += 1
        return {}

    monkeypatch.setattr(origin.importlib.metadata, "packages_distributions", packages_distributions)
    shared_entrypoint.PackageOrigin.read("fixture_package.module")
    monkeypatch.syspath_prepend(str(tmp_path))
    shared_entrypoint.PackageOrigin.read("fixture_package.module")
    shared_entrypoint.PackageOrigin.read("fixture_package.other")

    assert scans == 2


def test_package_index_can_be_refreshed_after_installation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index: dict[str, list[str]] = {}
    monkeypatch.setattr(origin.importlib.metadata, "packages_distributions", lambda: dict(index))
    monkeypatch.setattr(
        origin.importlib.metadata,
        "distribution",
        lambda name: types.SimpleNamespace(metadata={"Name": name}, version="1.2.3"),
    )
    assert shared_entrypoint.PackageOrigin.read("fixture_package").distribution is None
    index["fixture_package"] = ["fixture-distribution"]
    assert shared_entrypoint.PackageOrigin.read("fixture_package").distribution is None

    shared_entrypoint.PackageOrigin.invalidate_cache()

    assert shared_entrypoint.PackageOrigin.read("fixture_package") == (
        shared_entrypoint.PackageOrigin("fixture-distribution", "1.2.3")
    )


@pytest.mark.parametrize(
    ("package", "expected"),
    [
        (shared_entrypoint.PackageOrigin(None, None), "unavailable"),
        (shared_entrypoint.PackageOrigin("fixture-package", None), "fixture-package"),
        (shared_entrypoint.PackageOrigin("fixture-package", "1.0"), "fixture-package==1.0"),
    ],
)
def test_package_provenance_display(
    package: shared_entrypoint.PackageOrigin, expected: str
) -> None:
    assert str(package) == expected
