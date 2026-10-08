from pathlib import Path

from uptimely.spec import Specification

from .spec.spec import dataset_, dimensions

OUTPUT_PATH = Path(__file__).parent / "generated" / "spec.json"


def main() -> None:
    """Build the Python specification and export it as JSON."""
    specification = Specification.from_python(
        datasets=[dataset_],
        functions=dataset_.function_catalog(),
        dimensions=dimensions,
    )
    output_path = specification.to_json(OUTPUT_PATH)
    print(f"Specification written to {output_path}")


if __name__ == "__main__":
    main()
