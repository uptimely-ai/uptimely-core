import pathlib
from collections import abc

import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.codebase.python import entrypoint as shared_entrypoint
from uptimely.inspector import BindingInspection

SPEC_PATH = example_support.EXAMPLES_ROOT / "artifacts/build/spec.json"


pytestmark = pytest.mark.usefixtures("example_projects")


@pytest.fixture(autouse=True)
def isolate_package_index() -> abc.Iterator[None]:
    """Keep mocked distribution indexes separate from real environment metadata."""
    shared_entrypoint.PackageOrigin.invalidate_cache()
    yield
    shared_entrypoint.PackageOrigin.invalidate_cache()


def test_inspector_reports_unreadable_function_signatures() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions["ratio"].entrypoint = "invalid-entrypoint"

    with pytest.raises(ValueError, match="Invalid entrypoint 'invalid-entrypoint'"):
        BindingInspection.inspect_spec(spec_definition)


def test_inspector_still_checks_other_functions_when_a_signature_is_disabled() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions["ratio"].validate_signature = False
    spec_definition.functions["aggregate"].entrypoint = "uptimely_test_missing_dependency:calculate"

    with pytest.raises(
        ValueError, match="Could not read signature.*uptimely_test_missing_dependency"
    ):
        BindingInspection.inspect_spec(spec_definition)


def test_inspector_skips_disabled_return_annotation_validation(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_name = f"annotation_fixture_{tmp_path.name.replace('-', '_')}"
    package = tmp_path / package_name
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "calculation.py").write_text(
        "def calculate(**kwargs: object) -> int:\n    return 1\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    spec_definition = spec.load_spec(SPEC_PATH)
    function = spec_definition.functions["ratio"]
    function.entrypoint = f"{package_name}.calculation:calculate"
    function.validate_signature = False

    BindingInspection.inspect_spec(spec_definition)

    function.validate_signature = True
    with pytest.raises(ValueError, match="Python return annotation is int"):
        BindingInspection.inspect_spec(spec_definition)


def test_inspector_reports_unresolved_signature_annotations(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_name = f"unresolved_annotation_{tmp_path.name.replace('-', '_')}"
    package = tmp_path / package_name
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "calculation.py").write_text(
        "from __future__ import annotations\n"
        "def calculate(dataset: MissingAnnotation, **kwargs: object) -> object:\n"
        "    return object()\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions["ratio"].entrypoint = f"{package_name}.calculation:calculate"

    with pytest.raises(ValueError, match="Could not read signature.*MissingAnnotation"):
        BindingInspection.inspect_spec(spec_definition)


def test_inspector_reports_uninspectable_signatures(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_name = f"uninspectable_signature_{tmp_path.name.replace('-', '_')}"
    package = tmp_path / package_name
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "calculation.py").write_text(
        "class Implementation:\n"
        "    __signature__ = object()\n"
        "    def __call__(self, **kwargs: object) -> object:\n"
        "        return object()\n"
        "calculate = Implementation()\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions["ratio"].entrypoint = f"{package_name}.calculation:calculate"

    with pytest.raises(ValueError, match="Could not read signature"):
        BindingInspection.inspect_spec(spec_definition)
