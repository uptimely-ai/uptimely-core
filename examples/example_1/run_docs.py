from examples.example_1.common import GENERATED_DIR, load_specification

from uptimely.docs.docs import Documentation


def main() -> None:
    specification = load_specification()
    documentation = Documentation(specification)
    json_path = documentation.create_json(
        output_path=GENERATED_DIR / "docs" / "docs.json",
        include_generated_at=False,
    )
    html_path = documentation.create_html(
        output_path=GENERATED_DIR / "docs" / "docs.html",
        include_generated_at=False,
    )
    print(f"Documentation data written to {json_path}")
    print(f"HTML documentation written to {html_path}")


if __name__ == "__main__":
    main()
